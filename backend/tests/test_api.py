import time
from datetime import timedelta

import pytest

from app import db
from app.models import DiscoveredQuery, PipelineRun, utcnow
from app.utils.scoring import priority_for_score
from tests.conftest import PROFILE_PAYLOAD


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)


def wait_for_run(client, run_uuid, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        # The test keeps one app context (and session) open across requests, unlike a real
        # server; end its transaction so writes from the pipeline thread become visible.
        db.session.rollback()
        body = client.get(f"/api/v1/runs/{run_uuid}").get_json()
        if body["status"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError("pipeline run did not finish")


def test_create_profile_returns_201_with_normalised_fields(client):
    payload = dict(PROFILE_PAYLOAD, domain="SurferSEO.com",
                   competitors=["clearscope.io", "clearscope.io"])
    response = client.post("/api/v1/profiles", json=payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["domain"] == "surferseo.com"
    assert body["competitors"] == ["clearscope.io"]
    assert body["status"] == "created"


@pytest.mark.parametrize("override,field", [
    ({"domain": "http://surferseo.com"}, "domain"),
    ({"domain": "not a domain"}, "domain"),
    ({"name": ""}, "name"),
    ({"competitors": ["surferseo.com"]}, "competitors[0]"),
    ({"competitors": "clearscope.io"}, "competitors"),
])
def test_create_profile_validation_errors(client, override, field):
    response = client.post("/api/v1/profiles", json=dict(PROFILE_PAYLOAD, **override))

    assert_error(response, 400, "validation_error")
    assert field in response.get_json()["error"]["details"]


def test_unknown_uuids_return_404_json(client):
    assert_error(client.get("/api/v1/profiles/missing"), 404, "not_found")
    assert_error(client.post("/api/v1/queries/missing/recheck"), 404, "not_found")
    assert_error(client.get("/api/v1/runs/missing"), 404, "not_found")


@pytest.mark.parametrize("params", ["min_score=2", "min_score=abc", "status=hidden",
                                    "page=0", "per_page=500"])
def test_invalid_query_params_return_400(client, profile, params):
    response = client.get(f"/api/v1/profiles/{profile.uuid}/queries?{params}")
    assert_error(response, 400, "invalid_parameter")


def test_run_flow_filters_pagination_and_recommendations(client, profile, fake_llm):
    started = client.post(f"/api/v1/profiles/{profile.uuid}/run")
    assert started.status_code == 202
    assert_error(client.post(f"/api/v1/profiles/{profile.uuid}/run"), 409,
                 "pipeline_already_running")

    run = wait_for_run(client, started.get_json()["run_uuid"])
    assert run["status"] == "completed" and run["queries_scored"] == 12

    page = client.get(f"/api/v1/profiles/{profile.uuid}/queries?per_page=5&page=2").get_json()
    assert (page["page"], page["per_page"], page["total"], page["total_pages"]) == (2, 5, 12, 3)
    assert len(page["items"]) == 5
    assert {"query_uuid", "query_text", "estimated_search_volume", "competitive_difficulty",
            "opportunity_score", "domain_visible", "visibility_position",
            "discovered_at"} <= set(page["items"][0])

    visible = client.get(f"/api/v1/profiles/{profile.uuid}/queries?status=visible").get_json()
    assert visible["total"] == 4 and all(q["domain_visible"] is True for q in visible["items"])

    high = client.get(f"/api/v1/profiles/{profile.uuid}/queries?min_score=0.5").get_json()
    assert all(q["opportunity_score"] >= 0.5 for q in high["items"])

    queries = client.get(f"/api/v1/profiles/{profile.uuid}/queries?per_page=20").get_json()
    by_id = {item["query_uuid"]: item for item in queries["items"]}
    recs = client.get(f"/api/v1/profiles/{profile.uuid}/recommendations").get_json()
    assert recs["empty_reason"] is None and recs["total"] >= 1
    for item in recs["items"]:
        source = by_id[item["target_query_uuid"]]
        assert item["priority"] == priority_for_score(source["opportunity_score"])
        assert item["query_text"] == source["query_text"]
    assert {"recommendation_uuid", "target_query_uuid", "content_type", "title", "rationale",
            "target_keywords", "priority", "query_text"} <= set(recs["items"][0])


def test_stats_count_queries_from_the_latest_completed_run_only(client, profile):
    older = PipelineRun(profile_uuid=profile.uuid, status="completed", started_at=utcnow())
    db.session.add(older)
    db.session.flush()
    db.session.add(DiscoveredQuery(
        profile_uuid=profile.uuid, run_uuid=older.uuid, query_text="Old question?",
        opportunity_score=0.1, domain_visible=False,
    ))
    newer = PipelineRun(
        profile_uuid=profile.uuid, status="completed", started_at=utcnow() + timedelta(seconds=5),
    )
    failed = PipelineRun(
        profile_uuid=profile.uuid, status="failed", started_at=utcnow() + timedelta(seconds=10),
    )
    db.session.add_all([newer, failed])
    db.session.flush()
    db.session.add_all([
        DiscoveredQuery(
            profile_uuid=profile.uuid, run_uuid=newer.uuid, query_text="Current question?",
            opportunity_score=0.4, domain_visible=False,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid, run_uuid=newer.uuid, query_text="Another current question?",
            opportunity_score=0.6, domain_visible=True, visibility_position=1,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid, run_uuid=failed.uuid, query_text="Failed run question?",
            opportunity_score=0.9, domain_visible=False,
        ),
    ])
    db.session.commit()

    stats = client.get("/api/v1/stats").get_json()

    assert stats["total_profiles"] == 1
    assert stats["total_queries_discovered"] == 2
    assert stats["avg_opportunity_score"] == 0.5


def test_min_score_zero_keeps_queries_with_no_measured_demand(client, profile):
    run = PipelineRun(profile_uuid=profile.uuid, status="completed", started_at=utcnow())
    db.session.add(run)
    db.session.flush()
    db.session.add_all([
        DiscoveredQuery(
            profile_uuid=profile.uuid, run_uuid=run.uuid,
            query_text="Which company offers SaaS development?",
            search_keyword="saas development company",
            estimated_search_volume=None, competitive_difficulty=None,
            opportunity_score=None, domain_visible=False,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid, run_uuid=run.uuid, query_text="A measured question?",
            estimated_search_volume=2400, competitive_difficulty=40,
            opportunity_score=0.6, domain_visible=False,
        ),
    ])
    db.session.commit()

    included = client.get(f"/api/v1/profiles/{profile.uuid}/queries?min_score=0").get_json()
    assert included["total"] == 2

    filtered = client.get(f"/api/v1/profiles/{profile.uuid}/queries?min_score=0.5").get_json()
    assert [item["query_text"] for item in filtered["items"]] == ["A measured question?"]


def test_recommendations_explain_an_empty_list(client, profile):
    body = client.get(f"/api/v1/profiles/{profile.uuid}/recommendations").get_json()
    assert body["items"] == [] and body["empty_reason"] == "no_completed_run"


def test_cors_allows_the_angular_origin(client):
    response = client.options("/api/v1/profiles", headers={
        "Origin": "http://localhost:4200",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:4200"
