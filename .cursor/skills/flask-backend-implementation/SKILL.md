---
name: flask-backend-implementation
description: Step-by-step workflow for building the Flask AI Visibility Intelligence API — app factory, config, extensions, SQLAlchemy models, migrations, Blueprints, the six specified endpoints, filters/pagination, serialisation, and the consistent JSON error format. Use when creating or changing anything under backend/ other than agent internals.
---

# Flask Backend Implementation

Spec sections: "API Specification", "Database & Data Models", "Backend — Must Have",
"Suggested Project Structure", "Minimum Environment Variables" in
`.cursor/skills/assessment-requirements/reference.md`. Rules that apply:
`backend-flask-api.mdc`, `backend-data-models.mdc`.

## Workflow

```
- [ ] 1. Skeleton matching the suggested tree
- [ ] 2. Config + .env.example
- [ ] 3. create_app() + extensions + CORS + error handlers
- [ ] 4. Models + initial migration
- [ ] 5. Profiles Blueprint
- [ ] 6. Queries Blueprint
- [ ] 7. Wire pipeline endpoints to services/pipeline.py
- [ ] 8. Verify every endpoint and error path
```

### 1. Skeleton
```
backend/app/{__init__.py, models/, agents/, api/, services/, utils/}
backend/{tests/, migrations/, .env.example, requirements.txt}
```

### 2. Config
- Read `DATABASE_URL`, `FLASK_ENV`, `SECRET_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
  via python-dotenv. Default `DATABASE_URL=sqlite:///dev.db` as in the spec.
- A separate test config (in-memory or temp SQLite) for tests.

### 3. App factory
- `create_app(config=None)` initialises SQLAlchemy, Flask-Migrate, flask-cors, registers
  Blueprints under `/api/v1`, and registers JSON error handlers.
- One helper builds every error response:
```python
def error_response(status: int, code: str, message: str, details: dict | None = None):
    return jsonify({"error": {"code": code, "message": message, "details": details or {}}}), status
```

### 4. Models + migration
- Exact fields from the spec, UUID PKs, FKs, relationships (see `backend-data-models.mdc`).
- `flask db init` → `flask db migrate` → `flask db upgrade`; commit `migrations/`.

### 5. Profiles Blueprint (`api/profiles.py`)
| Endpoint | Success | Errors |
|---|---|---|
| `POST /profiles` | 201 + profile | 400 validation |
| `GET /profiles/<uuid>` | 200 + profile | 404 |
| `POST /profiles/<uuid>/run` | run object (code depends on sync/async decision) | 404, LLM failure handled |
| `GET /profiles/<uuid>/queries` | 200 + paginated queries | 400 bad params, 404 |
| `GET /profiles/<uuid>/recommendations` | 200 + list | 404 |

Queries filters: `min_score` (opportunity_score ≥ value), `status`
(`visible | not_visible | unknown`), `page`, `per_page` (spec example 20). Return
pagination metadata with the items.

### 6. Queries Blueprint (`api/queries.py`)
| Endpoint | Success | Errors |
|---|---|---|
| `POST /queries/<uuid>/recheck` | 200 + updated query object | 404, LLM failure handled |

### 7. Pipeline wiring
Blueprints call `services/pipeline.py`; they contain no agent logic. See the
`ai-agent-pipeline` skill.

### 8. Verify
- Every query object includes: `query_text`, `estimated_search_volume`,
  `competitive_difficulty`, `opportunity_score`, `domain_visible`, `visibility_position`,
  `discovered_at` (plus its uuid, needed for recheck — confirm field name with the user).
- Every recommendation includes: `recommendation_uuid`, `target_query_uuid`,
  `content_type`, `title`, `rationale`, `target_keywords`, `priority`.
- Unknown UUID → 404 JSON; malformed body/params → 400 JSON; no HTML errors anywhere.
- CORS preflight from `http://localhost:4200` succeeds.

## Extra endpoints
The dashboard (totals, recent runs) and bonus polling are not served by the six specified
endpoints. Add endpoints for them only after the user confirms the design; document them
in the README alongside the specified ones.
