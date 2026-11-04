import json

from pydantic import BaseModel, Field

from app.agents.base import AgentOutputError, BaseAgent, normalise_domain

MIN_QUERIES = 10
MAX_QUERIES = 20
MAX_BRANDED = 3

DISCOVERY_SYSTEM_PROMPT = f"""You are a search-intelligence analyst who studies what people ask AI \
assistants (ChatGPT, Claude, Perplexity) before buying software or services.

Task: given a business profile, write {MIN_QUERIES}-{MAX_QUERIES} realistic questions that potential \
customers would type into an AI assistant while researching products or services in this \
business's competitive space.

Requirements:
- Phrase each question the way a real user would ask an AI assistant (natural, conversational).
- Most real users do not know the brand yet. Write the questions with this intent mix:
  - about 40% category / "best X for Y" questions that name no brand at all,
  - about 25% problem or "how do I ..." questions that name no brand at all,
  - about 25% questions that name one or more of the listed competitors (comparisons, \
alternatives, reviews) without naming the business itself,
  - at most {MAX_BRANDED} questions that contain the business's own name.
- Use the industry and description to make questions specific to real use cases.
- Do not include years or dates.
- Every question must be unique and end with a question mark.

Output: respond with a single JSON object and nothing else, using exactly this schema:
{{
  "queries": [
    {{ "query_text": "string — one user question" }}
  ]
}}
The "queries" array must contain between {MIN_QUERIES} and {MAX_QUERIES} items."""


class DiscoveredQueryItem(BaseModel):
    query_text: str = Field(min_length=8, max_length=300)


class DiscoveryOutput(BaseModel):
    queries: list[DiscoveredQueryItem] = Field(min_length=1)


class QueryDiscoveryAgent(BaseAgent):
    name = "query_discovery"
    system_prompt = DISCOVERY_SYSTEM_PROMPT
    output_model = DiscoveryOutput
    temperature = 0.7

    def build_user_message(self, *, name: str, domain: str, industry: str,
                           description: str, competitors: list[str]) -> str:
        profile = {
            "name": name,
            "domain": domain,
            "industry": industry,
            "description": description,
            "competitors": competitors,
        }
        return "Business profile:\n" + json.dumps(profile, indent=2)

    def post_validate(self, output: DiscoveryOutput, *, name: str, domain: str,
                      **_inputs) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in output.queries:
            text = " ".join(item.query_text.split())
            key = text.lower().rstrip("?")
            if key not in seen:
                seen.add(key)
                unique.append(text)

        if len(unique) < MIN_QUERIES:
            raise AgentOutputError(
                f"expected at least {MIN_QUERIES} unique queries, got {len(unique)}"
            )

        brand_terms = {name.strip().lower(), normalise_domain(domain).split(".")[0]} - {""}
        branded = [q for q in unique if any(t in q.lower().replace(" ", "") or t in q.lower()
                                            for t in brand_terms)]
        unbranded = [q for q in unique if q not in branded]
        # Branded questions trivially surface the brand, so beyond the cap they only
        # displace real opportunities; drop the excess when enough queries remain.
        keep_branded = max(MAX_BRANDED, MIN_QUERIES - len(unbranded))
        kept = set(unbranded + branded[:keep_branded])
        return [q for q in unique if q in kept][:MAX_QUERIES]
