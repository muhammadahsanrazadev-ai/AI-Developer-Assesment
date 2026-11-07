import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from flask import Flask, current_app

from app import APIError, db
from app.agents import (
    AgentResult,
    ContentRecommendationAgent,
    KeywordAgent,
    LLMClient,
    LLMClientError,
    OpenAIClient,
    QueryDiscoveryAgent,
    VisibilityScoringAgent,
)
from app.models import BusinessProfile, ContentRecommendation, DiscoveredQuery, PipelineRun
from app.models import utcnow
from app.services.search_volume import SEO_API_MESSAGE, SearchVolumeError, build_volume_client
from app.utils.scoring import opportunity_score

logger = logging.getLogger(__name__)

SCORING_WORKERS = 5
RECOMMENDATION_INPUT_QUERIES = 5
STALE_RUN_AFTER = timedelta(minutes=15)
MAX_ERROR_LENGTH = 2000


def build_llm_client(app: Flask) -> LLMClient:
    return OpenAIClient(app.config["OPENAI_API_KEY"], app.config["OPENAI_MODEL"])


def start_pipeline(profile: BusinessProfile, background: bool = True) -> PipelineRun:
    _expire_stale_runs(profile)
    if any(run.status == "running" for run in profile.runs):
        raise APIError(409, "pipeline_already_running",
                       "A pipeline run is already in progress for this profile.")

    run = PipelineRun(profile_uuid=profile.uuid, status="running")
    profile.status = "running"
    db.session.add(run)
    db.session.commit()

    app = current_app._get_current_object()
    if background:
        threading.Thread(target=_run_in_app_context, args=(app, run.uuid),
                         daemon=True, name=f"pipeline-{run.uuid}").start()
    else:
        run_pipeline(run.uuid)
        db.session.refresh(run)
    return run


def _run_in_app_context(app: Flask, run_uuid: str) -> None:
    with app.app_context():
        run_pipeline(run_uuid)


def run_pipeline(run_uuid: str, llm_client: LLMClient | None = None) -> None:
    run = db.session.get(PipelineRun, run_uuid)
    if run is None:
        logger.error("Pipeline run %s not found", run_uuid)
        return
    profile = run.profile
    errors: list[str] = []
    failed = False

    try:
        try:
            volume_client = build_volume_client(current_app)
        except SearchVolumeError:
            failed = True
            errors.append(SEO_API_MESSAGE)
            return

        llm = llm_client or build_llm_client(current_app)

        discovery = QueryDiscoveryAgent(llm).run(
            name=profile.name, domain=profile.domain, industry=profile.industry,
            description=profile.description, competitors=list(profile.competitors or []),
        )
        _add_tokens(run, discovery)
        if not discovery.ok:
            failed = True
            errors.append(f"Query discovery failed: {discovery.error}")
            return

        keyword_result = KeywordAgent(llm).run(questions=list(discovery.data))
        _add_tokens(run, keyword_result)
        keywords = keyword_result.data if keyword_result.ok else {}
        if not keyword_result.ok:
            errors.append(f"Keyword generation failed: {keyword_result.error}")

        queries = [
            DiscoveredQuery(
                profile_uuid=profile.uuid, run_uuid=run.uuid, query_text=text,
                search_keyword=keywords.get(text),
            )
            for text in discovery.data
        ]
        db.session.add_all(queries)
        run.queries_discovered = len(queries)
        db.session.commit()

        try:
            metrics = volume_client.fetch([query.search_keyword for query in queries])
        except SearchVolumeError:
            failed = True
            errors.append(SEO_API_MESSAGE)
            return
        _attach_metrics(queries, metrics)
        db.session.commit()

        _score_queries(run, profile, queries, llm, errors)
        if run.queries_scored == 0:
            failed = True
            errors.insert(0, "Visibility scoring failed for every query.")
            return

        _recommend(run, profile, queries, llm, errors)

    except LLMClientError as exc:
        failed = True
        errors.append(f"LLM client error: {exc}")
    except SearchVolumeError:
        failed = True
        errors.append(SEO_API_MESSAGE)
    except Exception as exc:  # the run must always be finalised, whatever went wrong
        logger.exception("Pipeline run %s crashed", run_uuid)
        db.session.rollback()
        failed = True
        errors.append(f"Unexpected error: {type(exc).__name__}: {exc}")
    finally:
        _finalise(run_uuid, failed, errors)


def _score_queries(run: PipelineRun, profile: BusinessProfile, queries: list[DiscoveredQuery],
                   llm: LLMClient, errors: list[str]) -> None:
    agent = VisibilityScoringAgent(llm)
    jobs = {query.uuid: query.query_text for query in queries}
    by_uuid = {query.uuid: query for query in queries}

    with ThreadPoolExecutor(max_workers=SCORING_WORKERS) as pool:
        futures = {
            pool.submit(agent.run, query_text=text, industry=profile.industry,
                        target_domain=profile.domain, target_name=profile.name): uuid
            for uuid, text in jobs.items()
        }
        for future in as_completed(futures):
            query = by_uuid[futures[future]]
            try:
                result = future.result()
            except Exception as exc:
                result = AgentResult(ok=False, error=f"{type(exc).__name__}: {exc}")
            _add_tokens(run, result)
            if result.ok:
                apply_score(query, result.data)
                run.queries_scored += 1
            else:
                errors.append(f"Scoring failed for '{query.query_text[:60]}': {result.error}")
            db.session.commit()


def _attach_metrics(queries: list[DiscoveredQuery], metrics) -> None:
    for query in queries:
        item = metrics.get(query.search_keyword) if query.search_keyword else None
        if item is None:
            query.estimated_search_volume = None
            query.competitive_difficulty = None
            continue
        query.estimated_search_volume = item.search_volume
        query.competitive_difficulty = item.competition_index


def apply_score(query: DiscoveredQuery, score) -> None:
    query.domain_visible = score.domain_visible
    query.visibility_position = score.visibility_position
    if query.estimated_search_volume is None or query.competitive_difficulty is None:
        query.opportunity_score = None
        return
    query.opportunity_score = opportunity_score(
        query.estimated_search_volume, query.competitive_difficulty,
        score.domain_visible, score.visibility_position,
    )


def _recommend(run: PipelineRun, profile: BusinessProfile, queries: list[DiscoveredQuery],
               llm: LLMClient, errors: list[str]) -> None:
    gaps = sorted(
        (q for q in queries if q.domain_visible is False and q.opportunity_score is not None),
        key=lambda q: q.opportunity_score, reverse=True,
    )[:RECOMMENDATION_INPUT_QUERIES]
    if not gaps:
        logger.info("Run %s: domain visible for every scored query; no recommendations", run.uuid)
        _delete_run_recommendations(run)
        db.session.commit()
        return

    gap_queries = [
        {
            "query_uuid": q.uuid,
            "query_text": q.query_text,
            "opportunity_score": q.opportunity_score,
            "estimated_search_volume": q.estimated_search_volume,
            "competitive_difficulty": q.competitive_difficulty,
        }
        for q in gaps
    ]
    result = ContentRecommendationAgent(llm).run(profile=profile.to_dict(), gap_queries=gap_queries)
    _add_tokens(run, result)
    if not result.ok:
        errors.append(f"Content recommendation failed: {result.error}")
        db.session.commit()
        return

    _delete_run_recommendations(run)
    db.session.add_all(
        ContentRecommendation(
            profile_uuid=profile.uuid,
            query_uuid=item["target_query_uuid"],
            content_type=item["content_type"],
            title=item["title"],
            rationale=item["rationale"],
            target_keywords=item["target_keywords"],
            priority=item["priority"],
        )
        for item in result.data
    )
    db.session.commit()


def _delete_run_recommendations(run: PipelineRun) -> None:
    query_ids = db.session.query(DiscoveredQuery.uuid).filter_by(run_uuid=run.uuid)
    ContentRecommendation.query.filter(ContentRecommendation.query_uuid.in_(query_ids)).delete(
        synchronize_session="fetch"
    )


def _finalise(run_uuid: str, failed: bool, errors: list[str]) -> None:
    try:
        run = db.session.get(PipelineRun, run_uuid)
        run.status = "failed" if failed else "completed"
        run.error_message = "; ".join(errors)[:MAX_ERROR_LENGTH] or None
        run.completed_at = utcnow()
        run.profile.status = run.status
        db.session.commit()
    except Exception:
        logger.exception("Could not finalise pipeline run %s", run_uuid)
        db.session.rollback()


def _add_tokens(run: PipelineRun, result: AgentResult) -> None:
    run.tokens_used = (run.tokens_used or 0) + (result.tokens_used or 0)


def _expire_stale_runs(profile: BusinessProfile) -> None:
    cutoff = utcnow() - STALE_RUN_AFTER
    changed = False
    for run in profile.runs:
        started = run.started_at
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=cutoff.tzinfo)
        if run.status == "running" and started is not None and started < cutoff:
            run.status = "failed"
            run.error_message = "Run was interrupted before it finished."
            run.completed_at = utcnow()
            changed = True
    if changed:
        db.session.commit()


def recheck_query(query: DiscoveredQuery, llm_client: LLMClient | None = None) -> DiscoveredQuery:
    profile = query.profile
    keyword = query.search_keyword
    llm = llm_client
    if not keyword:
        try:
            llm = llm or build_llm_client(current_app)
        except LLMClientError as exc:
            raise APIError(502, "llm_unavailable", str(exc)) from exc
        generated = KeywordAgent(llm).run(questions=[query.query_text])
        _add_tokens(query.run, generated)
        if not generated.ok or not generated.data.get(query.query_text):
            db.session.commit()
            raise APIError(502, "keyword_failed", "Keyword generation failed.",
                           {"reason": generated.error})
        keyword = generated.data[query.query_text]

    try:
        metrics = build_volume_client(current_app).fetch([keyword])
    except SearchVolumeError as exc:
        db.session.rollback()
        raise APIError(502, "seo_api_unavailable", SEO_API_MESSAGE) from exc

    try:
        llm = llm or build_llm_client(current_app)
    except LLMClientError as exc:
        raise APIError(502, "llm_unavailable", str(exc)) from exc

    result = VisibilityScoringAgent(llm).run(
        query_text=query.query_text, industry=profile.industry,
        target_domain=profile.domain, target_name=profile.name,
    )
    _add_tokens(query.run, result)
    if not result.ok:
        db.session.commit()
        raise APIError(502, "recheck_failed", "Visibility recheck failed.",
                       {"reason": result.error})

    query.search_keyword = keyword
    item = metrics.get(keyword) if keyword else None
    if item is None:
        query.estimated_search_volume = None
        query.competitive_difficulty = None
    else:
        query.estimated_search_volume = item.search_volume
        query.competitive_difficulty = item.competition_index
    apply_score(query, result.data)
    errors: list[str] = []
    _recommend(query.run, profile, list(query.run.queries), llm, errors)
    if errors:
        existing = query.run.error_message or ""
        extra = "; ".join(errors)
        if extra not in existing:
            combined = f"{existing}; {extra}".strip("; ")
            query.run.error_message = combined[:MAX_ERROR_LENGTH]
        db.session.commit()
    return query
