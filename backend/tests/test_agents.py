import json

import pytest

from app.agents import (
    ContentRecommendationAgent,
    LLMClientError,
    QueryDiscoveryAgent,
    VisibilityScoringAgent,
)
from app.agents.base import LLMResponse, extract_json
from app.agents.base import AgentOutputError
from app.agents.discovery import (
    DiscoveryOutput,
    validate_business_relevance,
)
from tests.conftest import PROFILE_PAYLOAD, discovery_payload


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
    questions = [f"Which provider is the best SEO tool for use case {i}?" for i in range(n)]
    return discovery_payload(questions)


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


def _relevance(questions: list[str], **overrides):
    payload = json.loads(discovery_payload(questions, **overrides))
    output = DiscoveryOutput.model_validate(payload)
    profile = dict(PROFILE_PAYLOAD)
    return validate_business_relevance(
        output, name=profile["name"], domain=profile["domain"], industry=profile["industry"],
        description=profile["description"], competitors=profile["competitors"],
    )


def test_synonym_question_is_accepted_without_copying_the_profile_words():
    questions = [f"Who can help improve our search rankings for case {i}?" for i in range(9)]
    questions.append("Who should I hire to improve our search rankings?")
    saved = _relevance(questions)

    assert "SEO content optimization" not in saved[-1]
    assert saved[-1].startswith("Who should I hire")


def test_buyer_phrases_pass_and_a_definition_labeled_hire_fails():
    questions = [f"Where can I find a provider for case {i}?" for i in range(10)]
    assert len(_relevance(questions)) == 10

    commercial = questions[:-1] + ["Does Surfer SEO provide SEO content optimization?"]
    assert "Does Surfer SEO provide SEO content optimization?" in _relevance(commercial)

    choose = questions[:-1] + ["How do I choose an SEO tool?"]
    assert "How do I choose an SEO tool?" in _relevance(choose)

    lesson = questions[:-1] + ["What is involved in SEO?"]
    with pytest.raises(AgentOutputError, match="buyer question"):
        _relevance(lesson, intent="hire")

    diy = questions[:-1] + ["How do I build an SEO tool?"]
    with pytest.raises(AgentOutputError, match="buyer question"):
        _relevance(diy)

    missing_marks = [f"Where can I find a provider for case {i}" for i in range(10)]
    saved = _relevance(missing_marks)
    assert len(saved) == 10 and all(question.endswith("?") for question in saved)

    mixed = missing_marks + ["Clearscope vs MarketMuse: which provider is best"]
    assert len(_relevance(mixed)) == 10


def test_competitor_stems_use_word_boundaries():
    good = [f"Which provider is the best SEO tool for case {i}?" for i in range(9)]
    good.append("Who should I hire for a smart museum exhibit?")
    assert len(_relevance(good)) == 10

    software = good[:-1] + ["Which provider is best for arbisoftware?"]
    profile_competitors = ["arbisoft.com"]
    output = DiscoveryOutput.model_validate(json.loads(discovery_payload(software)))
    saved = validate_business_relevance(
        output, name="Surfer SEO", domain="surferseo.com", industry="SEO Software",
        description=PROFILE_PAYLOAD["description"], competitors=profile_competitors,
    )
    assert any("arbisoftware" in question for question in saved)

    named = good[:-1] + ["Which provider is best, Arbisoft?"]
    output = DiscoveryOutput.model_validate(json.loads(discovery_payload(named)))
    with pytest.raises(AgentOutputError, match="competitor"):
        validate_business_relevance(
            output, name="Surfer SEO", domain="surferseo.com", industry="SEO Software",
            description=PROFILE_PAYLOAD["description"], competitors=profile_competitors,
        )

    versus = good[:-1] + ["Clearscope vs MarketMuse: which provider is best?"]
    with pytest.raises(AgentOutputError, match="competitor"):
        _relevance(versus)

    comparison = good[:-1] + ["How does Surfer SEO compare to Clearscope?"]
    saved = _relevance(comparison)
    assert "How does Surfer SEO compare to Clearscope?" in saved

    both = good[:-1] + ["How does Surfer SEO compare to Clearscope and MarketMuse?"]
    with pytest.raises(AgentOutputError, match="exactly one competitor"):
        _relevance(both)


def test_offering_quote_must_be_copied_from_the_profile():
    questions = [f"Which provider is the best SEO tool for case {i}?" for i in range(10)]
    with pytest.raises(AgentOutputError, match="profile_quote"):
        _relevance(questions, offering={"label": "Catering", "profile_quote": "catering"})

    paraphrased = _relevance(
        questions, offering={"label": "SEO content optimization", "profile_quote": "SEO content optimisation"})
    assert len(paraphrased) == 10

    extra = json.loads(discovery_payload(questions))
    extra["offerings"].append({"label": "Catering", "profile_quote": "catering"})
    output = DiscoveryOutput.model_validate(extra)
    saved = validate_business_relevance(
        output, name=PROFILE_PAYLOAD["name"], domain=PROFILE_PAYLOAD["domain"],
        industry=PROFILE_PAYLOAD["industry"], description=PROFILE_PAYLOAD["description"],
        competitors=PROFILE_PAYLOAD["competitors"],
    )
    assert len(saved) == 10


def test_malformed_discovery_schema_is_retried_then_succeeds():
    missing_fields = json.dumps({"queries": [{"query_text": "Who should I hire for SEO?"}]})
    llm = Scripted(missing_fields, discovery_json(12))
    result = QueryDiscoveryAgent(llm).run(**PROFILE_PAYLOAD)

    assert result.ok and len(result.data) == 12
    assert result.attempts == 2


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


def test_scoring_matches_short_and_compact_brand_names():
    short = scoring_json(mentioned_brands=[{"name": "Surfer", "domain": ""}])
    compact = scoring_json(mentioned_brands=[{"name": "Surfer-SEO", "domain": "example.com"}])
    llm = Scripted(short, compact)
    agent = VisibilityScoringAgent(llm)

    first = agent.run(query_text="q?", industry="SEO", target_domain="surferseo.com",
                      target_name="Surfer SEO")
    second = agent.run(query_text="q?", industry="SEO", target_domain="surferseo.com",
                       target_name="Surfer SEO")

    assert first.ok and first.data.domain_visible is True and first.data.visibility_position == 1
    assert second.ok and second.data.domain_visible is True and second.data.visibility_position == 1


def test_scoring_reads_the_simulated_answer_when_the_brand_list_omits_it():
    payload = scoring_json(
        simulated_answer="Clearscope leads most answers, and Surfer is sometimes mentioned too.",
        mentioned_brands=[{"name": "Clearscope", "domain": "clearscope.io"}],
    )
    result = VisibilityScoringAgent(Scripted(payload)).run(
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

    two = ContentRecommendationAgent(Scripted(json.dumps(
        {"recommendations": [item("q1"), item("not-provided")]}
    ))).run(profile=PROFILE_PAYLOAD, gap_queries=gaps)
    assert two.ok and len(two.data) == 1

    bad = json.dumps({"recommendations": [item("q1", "video")] * 3})
    failed = ContentRecommendationAgent(Scripted(bad, bad)).run(profile=PROFILE_PAYLOAD,
                                                                gap_queries=gaps)
    assert not failed.ok and "content_type" in failed.error
