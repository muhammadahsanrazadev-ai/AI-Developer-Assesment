import json
import re
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base import AgentOutputError, BaseAgent, normalise_domain

MIN_QUERIES = 10
MAX_QUERIES = 20
MAX_BRANDED = 3

BuyerIntent = Literal["find_provider", "compare_options", "hire", "choose_provider"]

DISCOVERY_SYSTEM_PROMPT = f"""You are a search-intelligence analyst. You study what a potential customer \
asks an AI assistant (ChatGPT, Claude, Perplexity) while looking for a provider.

The business may be in any industry. Use only the name, domain, industry, and description \
you are given. Do not assume an industry, a service list, or a question template.

First, identify what this business actually sells. For each offering, copy profile_quote \
as a short contiguous phrase from the industry or the description, exactly as written. \
Do not paraphrase. If a phrase is not in that text, omit the offering.

Then write {MIN_QUERIES}-{MAX_QUERIES} questions a real buyer would ask. A question may use \
synonyms and natural customer language. It does not have to repeat the profile's words. \
Point every question at one offering_label you extracted.

Every question must be a buyer looking for a provider. Put a buyer phrase in the sentence, \
for example: who can help, where can I find, which company, which provider, who should I hire, \
who offers, looking for, hire, recommend, best, choose, pricing, offer, or provide.

Allowed: "Which company should a startup hire for this?", "Where can I find a provider?", \
"Does this company provide this service?", "What is the best provider for this?"
Not allowed: "What is involved?", "How do I build it myself?", "What are the benefits of a method?", \
or a definition that does not ask for a provider.

Rules:
- Most questions name no brand. At most {MAX_BRANDED} questions use the exact registered \
business name, and those must still be buyer questions.
- Do not name a competitor. Do not compare competitors. Do not review a competitor.
- Do not include years or dates.
- Every question is unique and ends with a question mark.
- intent is exactly one of: find_provider, compare_options, hire, choose_provider.

Output: one JSON object and nothing else:
{{
  "offerings": [
    {{ "label": "short offering", "profile_quote": "verbatim words from industry or description" }}
  ],
  "queries": [
    {{ "query_text": "one buyer question", "offering_label": "one label from offerings", "intent": "find_provider" }}
  ]
}}
The queries array must contain between {MIN_QUERIES} and {MAX_QUERIES} items."""

_BUYER_INTENT = re.compile(
    r"\bwho can help\b|"
    r"\bwho should i hire\b|"
    r"\bwhere can i find\b|"
    r"\bwhich (?:provider|company|companies|agency|vendor|firm|partner)\b|"
    r"\bwho (?:can|should|would|do|does|offers?|provides?)\b|"
    r"\blooking for\b|"
    r"\bfind a\b|"
    r"\b(?:hire|hiring)\b|"
    r"\brecommend(?:ed|ation)?\b|"
    r"\bbest\b|"
    r"\btop\b|"
    r"\bcompare\b|"
    r"\bchoose\b|"
    r"\bpricing\b|"
    r"\bquote\b|"
    r"\b(?:provider|agency|vendor)\b|"
    r"\b(?:offer|offers|offering|provide|provides|providing)\b|"
    r"\bwork with\b|"
    r"\boutsource\b|"
    r"\bpartner(?:ship)?\b",
    re.IGNORECASE,
)
_EDUCATIONAL = re.compile(
    r"\bhow (?:do|can) i (?:build|make|create|develop|implement|code|write|set up|setup)\b|"
    r"\bwhat is involved\b|"
    r"\bbenefits of\b|"
    r"\bpros and cons\b",
    re.IGNORECASE,
)
_DEFINITION = re.compile(r"\bwhat is\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_QUOTE_MATCH = 0.82


class Offering(BaseModel):
    label: str = Field(min_length=2, max_length=200)
    profile_quote: str = Field(min_length=2, max_length=500)


class DiscoveredQueryItem(BaseModel):
    query_text: str = Field(min_length=8, max_length=300)
    offering_label: str = Field(min_length=2, max_length=200)
    intent: BuyerIntent


class DiscoveryOutput(BaseModel):
    offerings: list[Offering] = Field(min_length=1)
    queries: list[DiscoveredQueryItem] = Field(min_length=1)


def competitor_stems(competitors, own_domain: str) -> set[str]:
    """Domain labels and stored names that must not appear as whole words."""
    own = normalise_domain(own_domain).split(".")[0]
    stems: set[str] = set()
    for item in competitors or []:
        domain = item
        name = ""
        if isinstance(item, dict):
            domain = str(item.get("domain") or "")
            name = str(item.get("name") or "")
        elif not isinstance(item, str):
            continue
        label = normalise_domain(str(domain)).split(".")[0]
        if len(label) >= 4 and label != own:
            stems.add(label)
        cleaned = " ".join(name.lower().split())
        if len(cleaned) >= 4:
            stems.add(cleaned)
    return stems


def contains_competitor(text: str, stems: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(stem)}\b", text, re.IGNORECASE) for stem in stems)


def is_buyer_intent(text: str) -> bool:
    return _BUYER_INTENT.search(text) is not None


def is_educational(text: str) -> bool:
    if _EDUCATIONAL.search(text):
        return True
    return _DEFINITION.search(text) is not None and not is_buyer_intent(text)


def _folded(text: str) -> str:
    return " ".join(_NON_ALNUM.sub(" ", text.lower()).split())


def _copied_quote(quote: str, industry: str, description: str) -> bool:
    """True when the quote is taken from the profile, allowing light paraphrase."""
    needle = _folded(quote)
    haystack = _folded(f"{industry} {description}")
    if not needle:
        return False
    if needle in haystack:
        return True
    words = haystack.split()
    count = len(needle.split())
    for size in {count, max(1, count - 1), count + 1}:
        if size > len(words):
            continue
        for index in range(len(words) - size + 1):
            window = " ".join(words[index:index + size])
            if SequenceMatcher(None, needle, window).ratio() >= _QUOTE_MATCH:
                return True
    return False


def _as_question(text: str) -> str:
    cleaned = " ".join(text.split()).rstrip(" ?!.")
    return f"{cleaned}?" if cleaned else ""


def validate_business_relevance(output: DiscoveryOutput, *, name: str, domain: str,
                                industry: str, description: str, competitors=None) -> list[str]:
    """Keep every valid buyer question. Fail only when fewer than 10 remain."""
    grounded: set[str] = set()
    for offering in output.offerings:
        if _copied_quote(offering.profile_quote, industry, description):
            grounded.add(" ".join(offering.label.lower().split()))

    stems = competitor_stems(competitors, domain)
    brand = " ".join(name.lower().split())
    seen: set[str] = set()
    unique: list[str] = []
    branded = 0
    dropped: list[str] = []
    for index, item in enumerate(output.queries, start=1):
        text = _as_question(item.query_text)
        key = text.lower().rstrip("?")
        if not text or key in seen:
            continue
        reasons: list[str] = []
        if " ".join(item.offering_label.lower().split()) not in grounded:
            reasons.append("profile_quote is not copied from the industry or description")
        if _YEAR.search(text):
            reasons.append("contains a year")
        if is_educational(text) or not is_buyer_intent(text):
            reasons.append("must be a buyer question, not a definition or a tutorial")
        if contains_competitor(text, stems):
            reasons.append("names a competitor")
        uses_brand = bool(brand) and brand in text.lower()
        if uses_brand and branded >= MAX_BRANDED:
            reasons.append(f"at most {MAX_BRANDED} questions may use the registered business name")
        if reasons:
            dropped.append(f"queries[{index}]: " + "; ".join(reasons) + ".")
            continue
        seen.add(key)
        unique.append(text)
        if uses_brand:
            branded += 1
        if len(unique) == MAX_QUERIES:
            break

    if len(unique) < MIN_QUERIES:
        detail = " ".join(dropped[:8]) if dropped else "no valid buyer questions remained."
        raise AgentOutputError(
            f"expected at least {MIN_QUERIES} unique queries, got {len(unique)}. {detail}"
        )
    return unique


class QueryDiscoveryAgent(BaseAgent):
    name = "query_discovery"
    system_prompt = DISCOVERY_SYSTEM_PROMPT
    output_model = DiscoveryOutput
    temperature = 0.4

    def build_user_message(self, *, name: str, domain: str, industry: str,
                           description: str, competitors=None, **_ignored) -> str:
        profile = {
            "name": name,
            "domain": domain,
            "industry": industry,
            "description": description,
        }
        return "Business profile:\n" + json.dumps(profile, indent=2)

    def post_validate(self, output: DiscoveryOutput, *, name: str, domain: str,
                      industry: str, description: str, competitors=None, **_ignored) -> list[str]:
        return validate_business_relevance(
            output, name=name, domain=domain, industry=industry,
            description=description, competitors=competitors,
        )
