import time

import pytest

from app import db
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

    recs = client.get(f"/api/v1/profiles/{profile.uuid}/recommendations").get_json()
    assert [r["priority"] for r in recs["items"]] == ["high", "high", "medium", "low"]
    assert {"recommendation_uuid", "target_query_uuid", "content_type", "title", "rationale",
            "target_keywords", "priority"} <= set(recs["items"][0])


def test_cors_allows_the_angular_origin(client):
    response = client.options("/api/v1/profiles", headers={
        "Origin": "http://localhost:4200",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:4200"
