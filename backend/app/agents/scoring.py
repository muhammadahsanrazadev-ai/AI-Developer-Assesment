import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent, normalise_domain

MAX_SEARCH_VOLUME = 10_000_000

# The target domain is deliberately NOT sent to the model, so the simulated answer is not
# biased toward the business being checked. Visibility is computed in code from the
# ordered list of brands the simulated answer mentions.
SCORING_SYSTEM_PROMPT = f"""You simulate how a typical AI assistant (ChatGPT, Claude, \
Perplexity) answers a user's question, and you estimate the search demand behind it.

Given a user question and its industry, do three things:
1. Write the answer a typical AI assistant would give today: neutral, helpful, 80-200 words, \
recommending or naming the products, tools, or companies it would normally mention.
2. List every brand / company mentioned in that answer, in the order they first appear, \
with its primary website domain (bare domain like "example.com", no protocol, no path).
3. Estimate demand and competition for this question:
   - estimated_search_volume: estimated monthly searches across search engines and AI \
assistants for this question and close variants (integer, 0-{MAX_SEARCH_VOLUME}).
   - competitive_difficulty: how hard it is for a new brand to get mentioned in answers to \
this question (integer 0-100; 0 = no established players, 100 = dominated by major brands).

Output: respond with a single JSON object and nothing else, using exactly this schema:
{{
  "simulated_answer": "string",
  "mentioned_brands": [
    {{ "name": "string", "domain": "string" }}
  ],
  "estimated_search_volume": 0,
  "competitive_difficulty": 0
}}
If the answer mentions no brands, return an empty "mentioned_brands" array."""


class MentionedBrand(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(default="", max_length=255)


class ScoringOutput(BaseModel):
    simulated_answer: str = Field(min_length=1)
    mentioned_brands: list[MentionedBrand] = Field(default_factory=list, max_length=50)
    estimated_search_volume: int = Field(ge=0, le=MAX_SEARCH_VOLUME)
    competitive_difficulty: int = Field(ge=0, le=100)


@dataclass
class VisibilityScore:
    estimated_search_volume: int
    competitive_difficulty: int
    domain_visible: bool
    visibility_position: int | None
    simulated_answer: str


class VisibilityScoringAgent(BaseAgent):
    name = "visibility_scoring"
    system_prompt = SCORING_SYSTEM_PROMPT
    output_model = ScoringOutput
    temperature = 0.3

    def build_user_message(self, *, query_text: str, industry: str, **_ignored) -> str:
        return json.dumps({"question": query_text, "industry": industry}, indent=2)

    def post_validate(self, output: ScoringOutput, *, target_domain: str,
                      target_name: str | None = None, **_ignored) -> VisibilityScore:
        position = find_position(
            output.mentioned_brands, target_domain, target_name, output.simulated_answer,
        )
        return VisibilityScore(
            estimated_search_volume=output.estimated_search_volume,
            competitive_difficulty=output.competitive_difficulty,
            domain_visible=position is not None,
            visibility_position=position,
            simulated_answer=output.simulated_answer,
        )


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _fold(value: str) -> str:
    return _NON_ALNUM.sub("", value.lower())


def names_match(candidate: str, business_name: str) -> bool:
    """True when the two names are the same brand, ignoring case, spaces, and hyphens.

    A shorter form matches when it is a prefix of the longer one and has at least
    four characters, so "Surfer" and "SurferSEO" both match "Surfer SEO".
    """
    left = _fold(candidate)
    right = _fold(business_name)
    if len(left) < 4 or len(right) < 4:
        return False
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return longer.startswith(shorter)


def _mention_span(answer: str, domain: str, name: str) -> tuple[int, int] | None:
    spans: list[tuple[int, int]] = []
    if domain:
        match = re.search(rf"(?<![a-z0-9]){re.escape(domain)}(?![a-z0-9])", answer, re.IGNORECASE)
        if match:
            spans.append(match.span())
    tokens = [token for token in _NON_ALNUM.split(name.lower()) if token]
    if tokens:
        flexible = r"[\s\-]*".join(re.escape(token) for token in tokens)
        match = re.search(rf"\b{flexible}\b", answer, re.IGNORECASE)
        if match:
            spans.append(match.span())
        if len(tokens[0]) >= 4:
            match = re.search(rf"\b{re.escape(tokens[0])}\b", answer, re.IGNORECASE)
            if match:
                spans.append(match.span())
    if not spans:
        return None
    return min(spans)


def _brand_span(answer: str, brand: MentionedBrand) -> tuple[int, int] | None:
    spans: list[tuple[int, int]] = []
    domain = normalise_domain(brand.domain) if brand.domain else ""
    if domain:
        match = re.search(rf"(?<![a-z0-9]){re.escape(domain)}(?![a-z0-9])", answer, re.IGNORECASE)
        if match:
            spans.append(match.span())
    if brand.name.strip():
        match = re.search(rf"\b{re.escape(brand.name.strip())}\b", answer, re.IGNORECASE)
        if match:
            spans.append(match.span())
    if not spans:
        return None
    return min(spans)


def find_position(brands: list[MentionedBrand], target_domain: str,
                  target_name: str | None, simulated_answer: str = "") -> int | None:
    domain = normalise_domain(target_domain)
    name = target_name or ""
    for index, brand in enumerate(brands, start=1):
        if brand.domain and normalise_domain(brand.domain) == domain:
            return index
        if name and names_match(brand.name, name):
            return index

    span = _mention_span(simulated_answer, domain, name)
    if span is None:
        return None
    earlier = sum(
        1 for brand in brands
        if (brand_span := _brand_span(simulated_answer, brand)) is not None and brand_span[0] < span[0]
    )
    return earlier + 1
