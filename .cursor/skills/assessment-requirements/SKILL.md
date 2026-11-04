---
name: assessment-requirements
description: Source-of-truth reference and compliance checklist for the AI Visibility Intelligence Platform assessment (Flask multi-agent API + Angular dashboard). Use when planning, implementing, or reviewing any feature, endpoint, model, screen, README, or submission item, or when the user asks whether something is required, optional, or matches the assessment.
---

# Assessment Requirements

The full specification is in [reference.md](reference.md). It is the single source of
truth. Read the relevant section of it before implementing or reviewing anything.

## How to use this skill

1. Locate the requirement in `reference.md` and quote it to yourself before coding.
2. Classify it: **Must Have**, **Required page/view detail**, or **Bonus (Nice to have)**.
3. If the spec is silent or ambiguous, check "Open decisions" below. Do not invent an
   answer; ask the user, then record the decision in the README "Tradeoffs" section.
4. After implementing, tick the matching items in the compliance checklist.

## Open decisions (spec is silent or ambiguous — confirm with the user)

| # | Gap in the spec | Why it matters |
|---|---|---|
| 1 | No endpoint lists profiles, pipeline runs, or aggregate stats | Dashboard needs totals and recent runs with zero mock data |
| 2 | No endpoint returns a single pipeline run's status | Needed for the bonus polling feature |
| 3 | Query object field list omits `uuid` | Recheck calls `/queries/{query_uuid}/recheck` |
| 4 | `domain_visible` is boolean, but filter accepts `unknown` | Defines how "unknown" is stored and returned |
| 5 | `BusinessProfile.status` values not defined | Model and UI need a fixed value set |
| 6 | `PipelineRun.status` values: only completed / failed / running are named | Partial-failure and pending states need a decision |
| 7 | 3–5 recommendations: per run or per query is not stated | Shapes Agent 3 input/output |
| 8 | Priority filter: client-side vs a server query param is not stated | Spec defines no param for recommendations |
| 9 | Sync vs async execution of `POST /run` | Long LLM runs; async is a listed bonus |
| 10 | Search volume source: "real data preferred" | Real data needs a third-party provider; otherwise LLM estimate |
| 11 | OpenAI or Anthropic (env example lists both keys) | Model selection must be documented in README |
| 12 | Opportunity score formula is "your formula" | Must be multi-factor, 0.0–1.0, documented |
| 13 | README text says `ng install && ng serve`; `ng install` is not an Angular CLI command | README command wording |
| 14 | "Angular Material illustration" for empty state; Material ships no illustrations | Choose an equivalent (icon/SVG) |
| 15 | Lazy-load "Queries", while Queries/Chart/Recommendations are tabs on Profile Detail | Routing structure for tabs |

## Compliance checklist

```
Backend — Must Have
- [ ] create_app() factory; Blueprints for profiles and queries
- [ ] SQLAlchemy models with all listed fields; UUID PKs; FKs + relationships
- [ ] Migrations (Flask-Migrate or Alembic) committed
- [ ] Three distinct agent classes (Discovery, Visibility Scoring, Content Recommendation)
- [ ] System prompts produce structured JSON with a defined schema
- [ ] Every AI response validated; bad LLM output never crashes the app
- [ ] Orchestrator handles partial failures and records run status/error_message
- [ ] All 6 endpoints exactly as specified, incl. min_score/status/page/per_page
- [ ] Query and recommendation objects contain every required field
- [ ] Proper HTTP status codes + one consistent error response format
- [ ] CORS via flask-cors; config via .env / python-dotenv
- [ ] Runnable via docker-compose up or a simple setup script
- [ ] Opportunity score: multi-factor, 0.0–1.0, documented, meaningful ordering

Frontend — Must Have
- [ ] Angular v17+, standalone components, TypeScript strict mode
- [ ] All 6 views: Dashboard, Profile Form, Profile Detail, Queries Table, Chart, Recommendations
- [ ] Zero hardcoded mock data; every value comes from the Flask API
- [ ] Reactive Forms only, validators, inline mat-error messages
- [ ] Typed interfaces for every API response shape
- [ ] All HTTP calls in Services; catchError with user-friendly messages
- [ ] Signals or BehaviorSubject for shared state
- [ ] Lazy-loaded routes for Dashboard, Profiles, Queries
- [ ] Loading, error, and empty states on every async operation
- [ ] MatSnackBar: pipeline started, pipeline complete, recheck done, errors
- [ ] Responsive at 1280px+ and 768px+

Delivery
- [ ] README: setup (backend + frontend), architecture, agent design, score formula,
      tradeoffs, model selection, AI tools used and for what
- [ ] backend/.env.example and frontend environment.ts example present
- [ ] Cold setup works in under 5 minutes
- [ ] Pushed to GitHub (private repo: hiring manager invited)

Bonus (only after Must Have is complete)
- [ ] Async pipeline    - [ ] Polling (interval + takeUntil)   - [ ] Dark mode toggle
- [ ] Docker            - [ ] CSV export (pipe/utility service) - [ ] Skeleton loaders
- [ ] Route animations  - [ ] Service unit tests                 - [ ] Loom walkthrough
```

## Priority by rubric weight

Agent architecture (20) → API design (15) → Prompt engineering (15) → Angular
completeness (15) → Data models (10) → API integration (10) → Score design (5) →
Code quality & README (5) → Bonus (+15).
