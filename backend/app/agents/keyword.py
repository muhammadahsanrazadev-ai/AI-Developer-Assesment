"""Turns each buyer question into one short Google keyword.

The model chooses the phrase. It does not estimate search volume or difficulty.
"""

import json
import re

from pydantic import BaseModel, Field

from app.agents.base import AgentOutputError, AgentResult, BaseAgent

MIN_WORDS = 2
MAX_WORDS = 4
MAX_CHARS = 80
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_WORD = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

KEYWORD_SYSTEM_PROMPT = f"""You turn buyer questions into the short phrase a person would type into Google.

For every question, write one keyword for that same intent.
Rules:
- {MIN_WORDS} to {MAX_WORDS} words
- lowercase
- keep a brand or product name when the question names one
- do not copy the whole question
- no question mark, no year, no extra commentary
- at most {MAX_CHARS} characters

Example:
Question: "Which company offers SaaS development?"
Keyword: "saas development company"

Output: one JSON object and nothing else:
{{
  "keywords": [
    {{ "query_text": "the question exactly as given", "search_keyword": "short keyword" }}
  ]
}}
Return one item for every question, using the question text unchanged."""


class KeywordItem(BaseModel):
    query_text: str = Field(min_length=1)
    search_keyword: str = Field(min_length=1, max_length=MAX_CHARS)


class KeywordOutput(BaseModel):
    keywords: list[KeywordItem] = Field(min_length=1, max_length=20)


def normalise_search_keyword(value: str) -> str:
    text = value.lower().replace("'", "").replace("\u2019", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _soft_question(value: str) -> str:
    return normalise_search_keyword(value)


def keyword_is_valid(value: str) -> bool:
    if _YEAR.search(value):
        return False
    words = value.split()
    if not MIN_WORDS <= len(words) <= MAX_WORDS or len(value) > MAX_CHARS:
        return False
    return all(_WORD.match(word) for word in words)


class KeywordAgent(BaseAgent):
    name = "keyword"
    system_prompt = KEYWORD_SYSTEM_PROMPT
    output_model = KeywordOutput
    temperature = 0.2

    def build_user_message(self, *, questions: list[str], **_ignored) -> str:
        return json.dumps({"questions": questions}, indent=2)

    def run(self, **inputs) -> AgentResult:
        self._usable: dict[str, str] = {}
        result = super().run(**inputs)
        if result.ok or not self._usable:
            return result
        # One bad phrase must not throw away the keywords that were already valid.
        return AgentResult(
            ok=True, data=self._usable, tokens_used=result.tokens_used, attempts=result.attempts,
        )

    def post_validate(self, output: KeywordOutput, *, questions: list[str], **_ignored) -> dict[str, str]:
        assigned = _assign_keywords(output.keywords, questions)
        usable = {
            question: keyword for question, keyword in assigned.items() if keyword_is_valid(keyword)
        }
        if len(usable) > len(self._usable):
            self._usable = usable
        if not usable:
            raise AgentOutputError("no keyword was 2 to 4 words")
        if len(usable) != len(questions):
            raise AgentOutputError(
                f"{len(questions) - len(usable)} keywords were not {MIN_WORDS} to {MAX_WORDS} words"
            )
        return usable


def _assign_keywords(items: list[KeywordItem], questions: list[str]) -> dict[str, str]:
    by_exact = {item.query_text: normalise_search_keyword(item.search_keyword) for item in items}
    by_soft: dict[str, str] = {}
    for item in items:
        by_soft.setdefault(_soft_question(item.query_text), normalise_search_keyword(item.search_keyword))

    assigned: dict[str, str] = {}
    for question in questions:
        if question in by_exact:
            assigned[question] = by_exact[question]
        elif _soft_question(question) in by_soft:
            assigned[question] = by_soft[_soft_question(question)]
    if len(assigned) < len(questions) and len(items) == len(questions):
        for question, item in zip(questions, items):
            assigned.setdefault(question, normalise_search_keyword(item.search_keyword))
    return assigned
