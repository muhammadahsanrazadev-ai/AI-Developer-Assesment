import json

import pytest

from app.agents.base import LLMResponse
from app.agents.keyword import KeywordAgent, keyword_is_valid, normalise_search_keyword
from app.services.search_volume import (
    DataForSEOVolumeClient,
    SearchVolumeError,
    build_volume_client,
    metrics_from_body,
)


class Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)

    def complete(self, system_prompt, user_message, temperature):
        response = self.responses.pop(0)
        return LLMResponse(response, 10)


def test_keyword_agent_accepts_a_short_google_phrase():
    question = "Which company offers SaaS development?"
    payload = json.dumps({"keywords": [{
        "query_text": question, "search_keyword": "SaaS Development Company",
    }]})
    result = KeywordAgent(Scripted(payload)).run(questions=[question])

    assert result.ok
    assert result.data == {question: "saas development company"}


def test_keyword_agent_rejects_a_long_phrase_then_keeps_a_short_one():
    question = "What is the best productivity tool for managing both personal and team projects?"
    long_phrase = json.dumps({"keywords": [{
        "query_text": question,
        "search_keyword": "best productivity tool managing both personal and team projects",
    }]})
    short_phrase = json.dumps({"keywords": [{
        "query_text": question, "search_keyword": "best productivity tool",
    }]})
    result = KeywordAgent(Scripted(long_phrase, short_phrase)).run(questions=[question])

    assert result.ok and result.attempts == 2
    assert result.data[question] == "best productivity tool"
    assert keyword_is_valid("best productivity tool")
    assert not keyword_is_valid("best productivity tool managing both personal and team projects")


def test_one_bad_keyword_does_not_drop_the_valid_ones():
    good = "Which company offers SaaS development?"
    bad = "What is the best productivity tool for managing both personal and team projects?"
    long_phrase = "best productivity tool managing both personal and team projects"
    payload = json.dumps({"keywords": [
        {"query_text": good, "search_keyword": "saas development company"},
        {"query_text": bad + " ", "search_keyword": long_phrase},
    ]})
    result = KeywordAgent(Scripted(payload, payload)).run(questions=[good, bad])

    assert result.ok
    assert result.data == {good: "saas development company"}


def test_a_domain_dot_is_removed_before_the_word_count():
    assert normalise_search_keyword("Coda.io alternatives") == "coda io alternatives"
    assert keyword_is_valid("coda io alternatives")


def test_response_keeps_only_valid_numbers_for_known_keywords():
    body = {
        "status_code": 20000,
        "tasks": [{
            "status_code": 20000,
            "result": [
                {"keyword": "saas development company", "search_volume": 2400,
                 "competition": "HIGH", "competition_index": 67},
                {"keyword": "missing demand", "search_volume": None, "competition_index": 10},
                {"keyword": "bad difficulty", "search_volume": 50, "competition_index": 250},
                {"keyword": "not requested", "search_volume": 9, "competition_index": 1},
            ],
        }],
    }
    metrics = metrics_from_body(body, {"saas development company", "missing demand", "bad difficulty"})

    assert metrics["saas development company"].search_volume == 2400
    assert metrics["saas development company"].competition_index == 67
    assert metrics["missing demand"].search_volume is None
    assert metrics["bad difficulty"].competition_index is None
    assert "not requested" not in metrics


def test_a_failed_task_is_an_outage():
    with pytest.raises(SearchVolumeError, match="SEO API not working properly"):
        metrics_from_body({"status_code": 40000, "tasks": []}, set())


def test_client_sends_each_keyword_once(monkeypatch):
    captured = {}

    class Response:
        def read(self):
            return json.dumps({
                "status_code": 20000,
                "tasks": [{"status_code": 20000, "result": [{
                    "keyword": "saas development company",
                    "search_volume": 2400.0,
                    "competition_index": 67,
                }]}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        assert "secret" not in request.full_url
        return Response()

    monkeypatch.setattr("app.services.search_volume.urllib.request.urlopen", fake_urlopen)
    client = DataForSEOVolumeClient("login", "secret", "https://api.dataforseo.com", 2840, "en")
    metrics = client.fetch(["saas development company", None, "saas development company"])

    assert captured["body"][0]["keywords"] == ["saas development company"]
    assert captured["body"][0]["location_code"] == 2840
    assert captured["timeout"] == 30
    assert metrics["saas development company"].search_volume == 2400


def test_bad_location_code_is_an_outage():
    app = type("App", (), {"config": {
        "DATAFORSEO_LOGIN": "login",
        "DATAFORSEO_PASSWORD": "secret",
        "DATAFORSEO_BASE_URL": "https://api.dataforseo.com",
        "DATAFORSEO_LOCATION_CODE": "US",
        "DATAFORSEO_LANGUAGE_CODE": "en",
    }})()

    with pytest.raises(SearchVolumeError):
        build_volume_client(app)
