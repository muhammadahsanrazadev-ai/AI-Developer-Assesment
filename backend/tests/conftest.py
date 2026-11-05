import json
import sys
from pathlib import Path

import pytest
from flask_migrate import upgrade

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app, db  # noqa: E402
from app.agents.base import LLMClientError, LLMResponse  # noqa: E402
from app.agents.discovery import DISCOVERY_SYSTEM_PROMPT  # noqa: E402
from app.agents.scoring import SCORING_SYSTEM_PROMPT  # noqa: E402
from app.models import BusinessProfile  # noqa: E402
from app.services import pipeline  # noqa: E402

PROFILE_PAYLOAD = {
    "name": "Surfer SEO",
    "domain": "surferseo.com",
    "industry": "SEO Software",
    "description": "AI-powered SEO content optimization tool",
    "competitors": ["clearscope.io", "marketmuse.com", "frase.io"],
}
SEO_OFFERING = {
    "label": "SEO content optimization",
    "profile_quote": "SEO content optimization",
}


def discovery_payload(questions: list[str], *, intent: str = "find_provider",
                      offering: dict | None = None) -> str:
    chosen = offering or SEO_OFFERING
    return json.dumps({
        "offerings": [chosen],
        "queries": [
            {"query_text": question, "offering_label": chosen["label"], "intent": intent}
            for question in questions
        ],
    })


class FakeLLM:
    """Scripted stand-in for OpenAIClient, routed by the agent's system prompt.

    Discovery returns 12 queries ("... case N?"). Scoring marks the target domain visible
    at position 1 for every third query and fails (invalid JSON) for indexes in
    ``failing_scores``. Recommendations target up to four of the gap queries it is given.
    """

    def __init__(self, *, discovery_error: bool = False, failing_scores: set[int] | None = None,
                 fail_all_scores: bool = False, recommendations_valid: bool = True):
        self.discovery_error = discovery_error
        self.failing_scores = failing_scores or set()
        self.fail_all_scores = fail_all_scores
        self.recommendations_valid = recommendations_valid

    def complete(self, system_prompt: str, user_message: str, temperature: float) -> LLMResponse:
        if system_prompt == DISCOVERY_SYSTEM_PROMPT:
            if self.discovery_error:
                raise LLMClientError("AuthenticationError: invalid api key")
            questions = [f"What is the best SEO tool for case {i}?" for i in range(12)]
            return LLMResponse(discovery_payload(questions), 100)

        if system_prompt == SCORING_SYSTEM_PROMPT:
            question = json.loads(user_message.split("\n\nYour previous")[0])["question"]
            index = int(question.split("case ")[1].rstrip("?"))
            if self.fail_all_scores or index in self.failing_scores:
                return LLMResponse("Sorry, I cannot help with that.", 10)
            brands = ([{"name": "Surfer SEO", "domain": "surferseo.com"}] if index % 3 == 0
                      else [{"name": "Clearscope", "domain": "clearscope.io"}])
            return LLMResponse(json.dumps({
                "simulated_answer": "Popular options include several tools.",
                "mentioned_brands": brands,
                "estimated_search_volume": 1000 * (index + 1),
                "competitive_difficulty": 40 + index,
            }), 50)

        if not self.recommendations_valid:
            return LLMResponse(json.dumps({"recommendations": []}), 30)
        gaps = json.loads(user_message.split("\n\nYour previous")[0])[
            "questions_where_business_is_not_visible"]
        return LLMResponse(json.dumps({"recommendations": [
            {
                "target_query_uuid": gap["query_uuid"],
                "content_type": "blog_post",
                "title": "How to choose an SEO content tool",
                "rationale": "Covers the question's intent where competitors dominate today.",
                "target_keywords": ["seo content tool"],
                "priority": priority,
            }
            for gap, priority in zip(gaps, ["low", "high", "medium", "high"])
        ]}), 70)


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "OPENAI_API_KEY": "",
    })
    with app.app_context():
        upgrade(directory=str(BACKEND_DIR / "migrations"))
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(pipeline, "build_llm_client", lambda _app: llm)
    return llm


@pytest.fixture
def profile(app):
    profile = BusinessProfile(**PROFILE_PAYLOAD)
    db.session.add(profile)
    db.session.commit()
    return profile
