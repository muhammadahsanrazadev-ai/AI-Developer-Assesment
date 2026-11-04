import json
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base import AgentOutputError, BaseAgent

MIN_RECOMMENDATIONS = 3
MAX_RECOMMENDATIONS = 5

RECOMMENDATION_SYSTEM_PROMPT = f"""You are a content strategist specialising in AI visibility: \
getting a brand cited in answers from AI assistants (ChatGPT, Claude, Perplexity).

You receive a business profile and a list of high-opportunity user questions where the \
business is currently NOT mentioned in AI answers. Each question has a "query_uuid".

Task: produce {MIN_RECOMMENDATIONS}-{MAX_RECOMMENDATIONS} specific, actionable content \
recommendations that would make AI assistants more likely to mention this business for those \
questions.

Each recommendation must:
- Target exactly one of the provided questions via its "query_uuid" (copy it verbatim).
- Say concretely what to create in "title" (a working title for the actual page or post).
- Explain in "rationale" why it closes the visibility gap for that question (2-4 sentences, \
referencing the question's intent and the competitors that currently own it).
- Choose "content_type" from: "blog_post", "landing_page", "faq".
- List 3-8 "target_keywords" (lowercase search phrases).
- Set "priority" to "high", "medium", or "low" based on opportunity score and effort.
Prefer the highest-opportunity questions. Avoid generic advice. Do not include years or \
dates in titles.
Titles must match how users phrase the question at category level (e.g. "How to Optimize \
Website Content for Search Engines: A Step-by-Step Guide"), because unbranded pages are what \
AI assistants cite for unbranded questions. Do not put the business's own brand name in the \
title; explain the brand's role in the rationale instead.

Output: respond with a single JSON object and nothing else, using exactly this schema:
{{
  "recommendations": [
    {{
      "target_query_uuid": "string",
      "content_type": "blog_post | landing_page | faq",
      "title": "string",
      "rationale": "string",
      "target_keywords": ["string"],
      "priority": "high | medium | low"
    }}
  ]
}}"""


class RecommendationItem(BaseModel):
    target_query_uuid: str
    content_type: Literal["blog_post", "landing_page", "faq"]
    title: str = Field(min_length=5, max_length=500)
    rationale: str = Field(min_length=10)
    target_keywords: list[str] = Field(min_length=1, max_length=10)
    priority: Literal["high", "medium", "low"]


class RecommendationOutput(BaseModel):
    recommendations: list[RecommendationItem] = Field(min_length=1)


class ContentRecommendationAgent(BaseAgent):
    name = "content_recommendation"
    system_prompt = RECOMMENDATION_SYSTEM_PROMPT
    output_model = RecommendationOutput
    temperature = 0.5

    def build_user_message(self, *, profile: dict, gap_queries: list[dict]) -> str:
        payload = {
            "business": {
                key: profile[key]
                for key in ("name", "domain", "industry", "description", "competitors")
            },
            "questions_where_business_is_not_visible": gap_queries,
        }
        return json.dumps(payload, indent=2)

    def post_validate(self, output: RecommendationOutput, *, gap_queries: list[dict],
                      **_ignored) -> list[dict]:
        allowed = {q["query_uuid"] for q in gap_queries}
        valid = []
        for item in output.recommendations:
            if item.target_query_uuid not in allowed:
                continue
            keywords = list(dict.fromkeys(k.strip().lower() for k in item.target_keywords if k.strip()))
            if not keywords:
                continue
            valid.append(item.model_copy(update={"target_keywords": keywords}).model_dump())

        if len(valid) < MIN_RECOMMENDATIONS:
            raise AgentOutputError(
                f"expected at least {MIN_RECOMMENDATIONS} recommendations that reference a "
                f"provided query_uuid, got {len(valid)}"
            )
        return valid[:MAX_RECOMMENDATIONS]
