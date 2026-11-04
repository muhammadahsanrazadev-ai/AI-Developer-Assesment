---
name: delivery-and-readme
description: Prepares the assessment for submission — docker-compose or setup script, environment example files, README with every required section, cold-run verification under 5 minutes, and GitHub submission. Use when writing or updating README files, docker-compose.yml, Dockerfiles, .env.example, environment.ts, or when preparing to submit.
---

# Delivery and README

Spec sections: "Backend — Must Have" items 8–10, "Frontend — Must Have" item 8,
"Minimum Environment Variables", "Submission Instructions", rubric row
"Code quality & README" in `.cursor/skills/assessment-requirements/reference.md`.
Rule that applies: `delivery-docs-setup.mdc`.

## Workflow

```
- [ ] 1. backend/.env.example and frontend environment files
- [ ] 2. docker-compose.yml (backend + frontend) or a simple setup script
- [ ] 3. README using the template below
- [ ] 4. Cold-run verification
- [ ] 5. Submission
```

### 1. Environment files
```
# backend/.env.example
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=sqlite:///dev.db
FLASK_ENV=development
SECRET_KEY=change-me
```
```ts
// frontend/src/environments/environment.ts
export const environment = { production: false, apiUrl: 'http://localhost:5000' };
```

### 2. Run setup
- `docker-compose up` starts backend (port 5000) and frontend together; migrations run
  automatically on backend start. If a setup script is used instead, it must be one
  simple command per platform.

### 3. README template
Confirmed with the user: there is **no root README**. The full template below lives in
`backend/README.md`; `frontend/README.md` covers frontend setup, `environment.ts`, scripts,
screens and structure, and links back to the backend README.

```markdown
# AI Visibility Intelligence Platform

## Overview
## Quick start (docker-compose up)
## Manual setup
### Backend (venv, install, .env, migrations, run)
### Frontend (install && serve)
## Architecture
## API reference (6 specified endpoints + any confirmed extras, with examples)
## Agent design
### Query Discovery Agent · Visibility Scoring Agent · Content Recommendation Agent
### Orchestrator and partial-failure handling
### Prompting, JSON schemas, validation and fallback
## Opportunity score formula (formula, factors, worked example, ordering rationale)
## AI model selection (provider, model, why)
## Tradeoffs and design decisions (every resolved spec gap)
## Bonus features implemented
## Testing
## AI tools used (which tools, for what)
```

### 4. Cold-run verification
- Fresh clone → follow README exactly → app works end-to-end in under 5 minutes.
- Only manual step allowed: copy `.env.example` to `.env` and add an API key.
- Create a profile, run the pipeline, view all three tabs, recheck a query.

### 5. Submission
- Push to GitHub (public or private; if private, invite the hiring manager).
- Confirm `.env` and real keys are not in the history.
- Submit the repository link via the portal or email provided.
