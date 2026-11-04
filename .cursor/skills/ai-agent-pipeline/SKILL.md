---
name: ai-agent-pipeline
description: Implements the three-agent AI pipeline (Query Discovery, Visibility Scoring, Content Recommendation), the shared base agent with JSON validation and fallback, the pipeline orchestrator with partial-failure handling, token tracking, recheck, and the opportunity score function. Use when working on backend/app/agents, backend/app/services/pipeline.py, backend/app/utils/scoring.py, LLM prompts, or the run/recheck endpoints.
---

# AI Agent Pipeline

Spec sections: "The Multi-Agent Pipeline", "Backend — Must Have" items 3–5, and rubric rows
"Agent architecture" (20), "Prompt engineering quality" (15), "Opportunity score design" (5)
in `.cursor/skills/assessment-requirements/reference.md`.

## Before coding — confirm with the user
- Provider: OpenAI (GPT-4o) or Anthropic (Claude).
- Sync vs async execution of `POST /run` (async is a bonus item).
- Search volume source ("real data preferred") vs LLM estimate.
- 3–5 recommendations per run or per query.
- How "unknown" visibility is represented.
- Opportunity score formula.

## Workflow

```
- [ ] 1. Base agent (agents/base.py)
- [ ] 2. Output schemas for each agent
- [ ] 3. Agent 1 — discovery.py
- [ ] 4. Agent 2 — scoring.py
- [ ] 5. Agent 3 — recommendation.py
- [ ] 6. Opportunity score (utils/scoring.py)
- [ ] 7. Orchestrator (services/pipeline.py)
- [ ] 8. Recheck flow
- [ ] 9. Verify failure paths
```

### 1. Base agent
Responsibilities, nothing else:
- Build messages (system prompt + user payload) and call the configured provider.
- Read token usage from the provider response and return it with the result.
- Extract JSON (strip markdown fences / leading prose if present), parse, validate
  against the agent's schema.
- Bounded retry on parse/validation failure (re-prompt including the validation error),
  then return a structured failure the caller can handle. Never raise to the HTTP layer.
- Catch provider errors (timeouts, rate limits, auth) and convert them to the same
  structured failure.

Shape of the return value (illustrative):
```python
AgentResult(ok: bool, data: dict | list | None, error: str | None, tokens_used: int)
```

### 2. Schemas
Define one explicit schema per agent output; prompts embed the same schema text so the
model and the validator agree. Enforce ranges and enums from the spec.

### 3. Agent 1 — Query Discovery
- Input: domain, industry, competitors (and name/description from the profile).
- Output: 10–20 realistic questions users ask AI assistants in this space, e.g.
  "What is the best SEO content tool?", "How does Surfer SEO compare to Clearscope?".
- Validate count (10–20), non-empty strings, de-duplicate.

### 4. Agent 2 — Visibility Scoring
- Input: one query + target domain (competitors may help the simulation).
- Simulate an AI-generated answer and determine whether the target domain appears and
  at which position (`visibility_position` integer or null).
- Output per query: `estimated_search_volume`, `competitive_difficulty` (0–100),
  `domain_visible`, `visibility_position`. The orchestrator computes `opportunity_score`.
- Per-query failure is isolated (see step 7).

### 5. Agent 3 — Content Recommendation
- Input: top-scoring queries where `domain_visible` is false.
- Output: 3–5 recommendations, each with `target_query_uuid`, `content_type`
  (`blog_post | landing_page | faq`), `title`, `rationale` (why it helps),
  `target_keywords` (list), `priority` (`high | medium | low`).
- Validate that every `target_query_uuid` refers to a query that was actually given.
- If there are no non-visible queries, skip the agent and record that cleanly.

### 6. Opportunity score
- Pure function, deterministic, returns a float clamped to 0.0–1.0.
- Multi-factor and based on "search volume × competitive gap" (spec). Visibility should
  influence the score so that gaps rank higher — confirm the exact formula with the user.
- Document: formula, each factor's normalisation, a worked example, and why the ordering
  is meaningful.

### 7. Orchestrator
```
create PipelineRun(status=running, started_at=now)
try:
  discovery = Agent1.run(profile)          # failure here → run failed, stop
  persist queries; queries_discovered = n
  for each query:
     result = Agent2.run(query, domain)     # failure → note it, continue
     if ok: compute opportunity_score, persist, queries_scored += 1
  top_gaps = highest-scoring non-visible queries
  Agent3.run(top_gaps)                      # failure → note it, keep scored queries
  persist recommendations
finally:
  set status, error_message, tokens_used (sum of all calls), completed_at
```
- The final status must reflect partial failures distinctly from full success. Which
  status values to use is an open decision — confirm with the user.
- Commit results so a crash mid-run never leaves a run stuck in `running`.

### 8. Recheck
`POST /api/v1/queries/{query_uuid}/recheck` → rerun Agent 2 for that query, recompute
`opportunity_score`, update the row, return the updated query object.

### 9. Verify failure paths
Exercise with a stubbed LLM client: invalid JSON, fenced JSON, missing fields, wrong
enum, out-of-range numbers, wrong item count, provider exception. Each must end in a
handled outcome and a correctly finalised `PipelineRun`.
