import pytest

from app import APIError, db
from app.models import ContentRecommendation, DiscoveredQuery, PipelineRun
from app.services import pipeline
from tests.conftest import FakeLLM


def run_with(profile, llm) -> PipelineRun:
    run = PipelineRun(profile_uuid=profile.uuid)
    db.session.add(run)
    db.session.commit()
    pipeline.run_pipeline(run.uuid, llm_client=llm)
    db.session.expire_all()
    return db.session.get(PipelineRun, run.uuid)


def test_successful_run_persists_queries_scores_and_recommendations(profile):
    run = run_with(profile, FakeLLM())

    assert run.status == "completed" and run.completed_at is not None
    assert run.queries_discovered == run.queries_scored == 12
    assert run.tokens_used > 0 and run.error_message is None
    assert run.profile.status == "completed"
    assert ContentRecommendation.query.filter_by(profile_uuid=profile.uuid).count() == 4


def test_partial_scoring_failure_keeps_the_rest_of_the_run(profile):
    run = run_with(profile, FakeLLM(failing_scores={1, 5, 7}))

    assert run.status == "completed"
    assert run.queries_discovered == 12 and run.queries_scored == 9
    assert run.error_message.count("Scoring failed") == 3
    unknown = DiscoveredQuery.query.filter_by(run_uuid=run.uuid, domain_visible=None).count()
    assert unknown == 3


def test_discovery_failure_marks_run_failed(profile):
    run = run_with(profile, FakeLLM(discovery_error=True))

    assert run.status == "failed" and run.completed_at is not None
    assert "Query discovery failed" in run.error_message
    assert run.profile.status == "failed"


def test_all_scoring_failing_marks_run_failed(profile):
    run = run_with(profile, FakeLLM(fail_all_scores=True))

    assert run.status == "failed"
    assert run.error_message.startswith("Visibility scoring failed for every query")


def test_recommendation_failure_still_completes_with_scores(profile):
    run = run_with(profile, FakeLLM(recommendations_valid=False))

    assert run.status == "completed" and run.queries_scored == 12
    assert "Content recommendation failed" in run.error_message
    assert ContentRecommendation.query.count() == 0


def test_recheck_failure_raises_502_and_keeps_existing_score(profile):
    run = run_with(profile, FakeLLM())
    query = DiscoveredQuery.query.filter_by(run_uuid=run.uuid).first()
    before = query.opportunity_score

    with pytest.raises(APIError) as exc:
        pipeline.recheck_query(query, llm_client=FakeLLM(fail_all_scores=True))

    assert exc.value.status == 502
    assert query.opportunity_score == before
