import json

import pytest

from app.agents import (
    ContentRecommendationAgent,
    LLMClientError,
    QueryDiscoveryAgent,
    VisibilityScoringAgent,
)
from app.agents.base import LLMResponse, extract_json
from tests.conftest import PROFILE_PAYLOAD


class Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system_prompt, user_message, temperature):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMResponse(response, 10)


def discovery_json(n: int) -> str:
    return json.dumps({"queries": [{"query_text": f"Which SEO tool fits use case {i}?"}
                                   for i in range(n)]})


def scoring_json(**overrides) -> str:
    body = {
        "simulated_answer": "Clearscope and Surfer SEO are common picks.",
        "mentioned_brands": [{"name": "Clearscope", "domain": "clearscope.io"},
                             {"name": "Surfer SEO", "domain": "https://www.SurferSEO.com/pricing"}],
        "estimated_search_volume": 2400,
        "competitive_difficulty": 70,
    }
    body.update(overrides)
    return json.dumps(body)


@pytest.mark.parametrize("content", [
    '```json\n{"a": 1}\n```',
    'Here is the result: {"a": 1} Hope it helps!',
    '{"a": 1}',
])
def test_extract_json_handles_fences_and_surrounding_prose(content):
    assert extract_json(content) == {"a": 1}


def test_invalid_json_is_retried_with_feedback_then_succeeds():
    llm = Scripted("I think the answer is...", discovery_json(12))
    result = QueryDiscoveryAgent(llm).run(**PROFILE_PAYLOAD)

    assert result.ok and len(result.data) == 12
    assert result.attempts == 2 and result.tokens_used == 20


def test_persistently_bad_output_returns_failure_instead_of_raising():
    llm = Scripted(discovery_json(3), discovery_json(3))
    result = QueryDiscoveryAgent(llm).run(**PROFILE_PAYLOAD)

    assert not result.ok
    assert "at least 10" in result.error
    assert llm.calls == 2


def test_provider_error_is_returned_as_failure():
    llm = Scripted(LLMClientError("RateLimitError: slow down"))
    result = QueryDiscoveryAgent(llm).run(**PROFILE_PAYLOAD)

    assert not result.ok and "RateLimitError" in result.error


def test_scoring_rejects_out_of_range_difficulty():
    llm = Scripted(scoring_json(competitive_difficulty=250), scoring_json(competitive_difficulty=250))
    result = VisibilityScoringAgent(llm).run(query_text="q?", industry="SEO",
                                             target_domain="surferseo.com")

    assert not result.ok and "competitive_difficulty" in result.error


def test_scoring_finds_target_position_from_normalised_domains():
    result = VisibilityScoringAgent(Scripted(scoring_json())).run(
        query_text="q?", industry="SEO", target_domain="surferseo.com", target_name="Surfer SEO")

    assert result.ok
    assert result.data.domain_visible is True
    assert result.data.visibility_position == 2


def test_recommendations_drop_unknown_query_uuids_and_bad_enums_fail():
    gaps = [{"query_uuid": "q1", "query_text": "a?"}, {"query_uuid": "q2", "query_text": "b?"}]

    def item(uuid, content_type="faq"):
        return {"target_query_uuid": uuid, "content_type": content_type, "title": "A useful guide",
                "rationale": "Closes the gap for this question.", "target_keywords": ["SEO Tool"],
                "priority": "high"}

    ok = ContentRecommendationAgent(Scripted(json.dumps(
        {"recommendations": [item("q1"), item("q2"), item("q1"), item("not-provided")]}
    ))).run(profile=PROFILE_PAYLOAD, gap_queries=gaps)
    assert ok.ok and len(ok.data) == 3
    assert {r["target_query_uuid"] for r in ok.data} <= {"q1", "q2"}
    assert ok.data[0]["target_keywords"] == ["seo tool"]

    bad = json.dumps({"recommendations": [item("q1", "video")] * 3})
    failed = ContentRecommendationAgent(Scripted(bad, bad)).run(profile=PROFILE_PAYLOAD,
                                                                gap_queries=gaps)
    assert not failed.ok and "content_type" in failed.error
