import math
import re

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func

from app import APIError, db
from app.models import BusinessProfile, ContentRecommendation, DiscoveredQuery, PipelineRun
from app.services import pipeline

profiles_bp = Blueprint("profiles", __name__)

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
VISIBILITY_STATUSES = ("visible", "not_visible", "unknown")
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100
DEFAULT_RUNS_LIMIT = 10
MAX_RUNS_LIMIT = 50
MAX_COMPETITORS = 10
TEXT_LIMITS = {"name": 255, "industry": 255, "description": 5000}
PRIORITY_ORDER = case({"high": 0, "medium": 1, "low": 2}, value=ContentRecommendation.priority)


@profiles_bp.post("/profiles")
def create_profile():
    data = _validate_profile_payload(request.get_json(silent=True))
    profile = BusinessProfile(**data)
    db.session.add(profile)
    db.session.commit()
    return jsonify(profile.to_dict()), 201


@profiles_bp.get("/profiles")
def list_profiles():
    profiles = BusinessProfile.query.order_by(BusinessProfile.created_at.desc()).all()
    return jsonify({"items": [p.to_dict() for p in profiles], "total": len(profiles)})


@profiles_bp.get("/profiles/<profile_uuid>")
def get_profile(profile_uuid: str):
    return jsonify(_get_profile_or_404(profile_uuid).to_dict())


@profiles_bp.post("/profiles/<profile_uuid>/run")
def run_profile_pipeline(profile_uuid: str):
    run = pipeline.start_pipeline(_get_profile_or_404(profile_uuid))
    return jsonify(run.to_dict()), 202


@profiles_bp.get("/profiles/<profile_uuid>/queries")
def list_profile_queries(profile_uuid: str):
    profile = _get_profile_or_404(profile_uuid)
    min_score = _float_param("min_score", 0.0, 1.0)
    status = request.args.get("status")
    if status is not None and status not in VISIBILITY_STATUSES:
        raise APIError(400, "invalid_parameter",
                       f"status must be one of: {', '.join(VISIBILITY_STATUSES)}.",
                       {"status": status})
    page = _int_param("page", 1, 1, None)
    per_page = _int_param("per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)

    run = _latest_completed_run(profile)
    if run is None:
        return jsonify(_page_body([], page, per_page, 0, run_uuid=None))

    query = DiscoveredQuery.query.filter_by(run_uuid=run.uuid)
    if min_score is not None:
        query = query.filter(DiscoveredQuery.opportunity_score >= min_score)
    if status == "visible":
        query = query.filter(DiscoveredQuery.domain_visible.is_(True))
    elif status == "not_visible":
        query = query.filter(DiscoveredQuery.domain_visible.is_(False))
    elif status == "unknown":
        query = query.filter(DiscoveredQuery.domain_visible.is_(None))

    total = query.count()
    items = (
        query.order_by(DiscoveredQuery.opportunity_score.is_(None),
                       DiscoveredQuery.opportunity_score.desc(),
                       DiscoveredQuery.discovered_at)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return jsonify(_page_body([q.to_dict() for q in items], page, per_page, total, run.uuid))


@profiles_bp.get("/profiles/<profile_uuid>/recommendations")
def list_profile_recommendations(profile_uuid: str):
    profile = _get_profile_or_404(profile_uuid)
    run = _latest_completed_run(profile)
    items = []
    if run is not None:
        items = (
            ContentRecommendation.query
            .join(DiscoveredQuery, ContentRecommendation.query_uuid == DiscoveredQuery.uuid)
            .filter(DiscoveredQuery.run_uuid == run.uuid)
            .order_by(PRIORITY_ORDER, ContentRecommendation.created_at)
            .all()
        )
    return jsonify({
        "items": [r.to_dict() for r in items],
        "total": len(items),
        "run_uuid": run.uuid if run else None,
    })


@profiles_bp.get("/stats")
def get_stats():
    avg_score = db.session.query(func.avg(DiscoveredQuery.opportunity_score)).scalar()
    return jsonify({
        "total_profiles": BusinessProfile.query.count(),
        "total_queries_discovered": DiscoveredQuery.query.count(),
        "avg_opportunity_score": round(avg_score, 4) if avg_score is not None else None,
    })


@profiles_bp.get("/runs")
def list_runs():
    limit = _int_param("limit", DEFAULT_RUNS_LIMIT, 1, MAX_RUNS_LIMIT)
    query = PipelineRun.query
    profile_uuid = request.args.get("profile_uuid")
    if profile_uuid:
        _get_profile_or_404(profile_uuid)
        query = query.filter_by(profile_uuid=profile_uuid)
    runs = query.order_by(PipelineRun.started_at.desc()).limit(limit).all()
    return jsonify({"items": [_run_with_profile(r) for r in runs], "total": len(runs)})


@profiles_bp.get("/runs/<run_uuid>")
def get_run(run_uuid: str):
    run = db.session.get(PipelineRun, run_uuid)
    if run is None:
        raise APIError(404, "not_found", "Pipeline run not found.", {"run_uuid": run_uuid})
    return jsonify(_run_with_profile(run))


def _get_profile_or_404(profile_uuid: str) -> BusinessProfile:
    profile = db.session.get(BusinessProfile, profile_uuid)
    if profile is None:
        raise APIError(404, "not_found", "Business profile not found.",
                       {"profile_uuid": profile_uuid})
    return profile


def _latest_completed_run(profile: BusinessProfile) -> PipelineRun | None:
    return (
        PipelineRun.query
        .filter_by(profile_uuid=profile.uuid, status="completed")
        .order_by(PipelineRun.started_at.desc())
        .first()
    )


def _run_with_profile(run: PipelineRun) -> dict:
    body = run.to_dict()
    body["profile_name"] = run.profile.name
    body["profile_domain"] = run.profile.domain
    return body


def _page_body(items: list, page: int, per_page: int, total: int, run_uuid: str | None) -> dict:
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": math.ceil(total / per_page) if total else 0,
        "run_uuid": run_uuid,
    }


def _int_param(name: str, default: int, minimum: int, maximum: int | None) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise APIError(400, "invalid_parameter", f"{name} must be an integer.", {name: raw})
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"between {minimum} and {maximum}" if maximum else f"at least {minimum}"
        raise APIError(400, "invalid_parameter", f"{name} must be {bounds}.", {name: raw})
    return value


def _float_param(name: str, minimum: float, maximum: float) -> float | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except ValueError:
        raise APIError(400, "invalid_parameter", f"{name} must be a number.", {name: raw})
    if math.isnan(value) or not minimum <= value <= maximum:
        raise APIError(400, "invalid_parameter",
                       f"{name} must be between {minimum} and {maximum}.", {name: raw})
    return value


def _validate_profile_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise APIError(400, "invalid_json", "Request body must be a JSON object.")

    errors: dict[str, str] = {}
    data: dict = {}

    for field, limit in TEXT_LIMITS.items():
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors[field] = "This field is required."
        elif len(value.strip()) > limit:
            errors[field] = f"Must be at most {limit} characters."
        else:
            data[field] = value.strip()

    domain = payload.get("domain")
    domain_error = _domain_error(domain)
    if domain_error:
        errors["domain"] = domain_error
    else:
        data["domain"] = domain.strip().lower()

    competitors = payload.get("competitors", [])
    if not isinstance(competitors, list):
        errors["competitors"] = "Must be a list of domains."
    elif len(competitors) > MAX_COMPETITORS:
        errors["competitors"] = f"At most {MAX_COMPETITORS} competitors are allowed."
    else:
        cleaned: list[str] = []
        for index, competitor in enumerate(competitors):
            error = _domain_error(competitor)
            if error:
                errors[f"competitors[{index}]"] = error
                continue
            value = competitor.strip().lower()
            if value == data.get("domain"):
                errors[f"competitors[{index}]"] = "A competitor cannot be the business's own domain."
            elif value not in cleaned:
                cleaned.append(value)
        data["competitors"] = cleaned

    if errors:
        raise APIError(400, "validation_error", "Some fields are invalid.", errors)
    return data


def _domain_error(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "This field is required."
    value = value.strip().lower()
    if "://" in value:
        return "Enter the domain only, without http:// or https:// (e.g. example.com)."
    if not DOMAIN_RE.match(value):
        return "Enter a valid domain like example.com (no paths or spaces)."
    return None
