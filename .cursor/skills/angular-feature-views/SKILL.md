---
name: angular-feature-views
description: Per-screen requirements and build workflow for the six Angular views (Dashboard, Business Profile Form, Profile Detail, Queries Table, Opportunity Score Chart, Recommendations), plus project setup, services, typed models, routing, and lazy loading. Use when creating or changing anything under frontend/, or when the user mentions a screen, page, view, tab, chart, table, or form.
---

# Angular Feature Views

Spec sections: "Part 2 — Frontend Dashboard", "Angular-Specific Requirements",
"UI/UX Requirements", "Frontend — Must Have" in
`.cursor/skills/assessment-requirements/reference.md`. Rules that apply:
`frontend-angular-standards.mdc`, `frontend-ui-ux.mdc`.

## Setup workflow

```
- [ ] 1. Angular v17+ workspace in frontend/, standalone, strict mode
- [ ] 2. UI library (Angular Material or TailwindCSS — confirm) + chart lib (ng2-charts or ngx-charts — confirm)
- [ ] 3. environments/environment.ts + environment.prod.ts (apiUrl)
- [ ] 4. shared/models interfaces mirroring backend JSON
- [ ] 5. core/services: ProfileService, QueryService, PipelineService
- [ ] 6. app.routes.ts with lazy-loaded Dashboard, Profiles, Queries
- [ ] 7. Build views below, one at a time
```

The spec names many Angular Material components (mat-error, mat-table, MatPaginator,
mat-slider, mat-select, mat-card, mat-button-toggle-group, MatSnackBar, progress spinner).
If TailwindCSS is chosen instead, each must have a functional equivalent.

## Views (every view: loading, error, empty states; data only from the API)

### 1. Dashboard / Home
- Summary stats: total profiles, total queries discovered, avg opportunity score.
- Recent pipeline runs list with status (completed / failed / running).
- "Add New Business Profile" button → profile form route.
- Data source needs endpoints beyond the six specified — confirm with the user first.

### 2. Business Profile Form
- Reactive Form fields: Business Name, Domain, Industry, Description, Competitors
  (chip/tag input).
- Validators: required fields; domain format — bare domain like `domain.com`, reject
  `http://` / `https://`. Whether competitor entries get the same domain validation is
  not stated in the spec — confirm with the user.
- Inline errors with `mat-error` (or equivalent).
- Submit → `ProfileService` → `POST /api/v1/profiles` → navigate to Profile Detail of the
  created profile. Disable submit while saving; snackbar on success/error.

### 3. Profile Detail
- Shows name, domain, industry, description, competitors as chips.
- "Run Pipeline" → `POST /api/v1/profiles/{uuid}/run`. While running: button disabled +
  Material progress spinner. Snackbar: pipeline started / complete / error.
- After completion: summary card with queries discovered, queries scored, tokens used.
- Tab navigation: Queries, Chart, Recommendations. Tabs refresh after a run completes.

### 4. Queries Table (tab)
- `mat-table` + `MatPaginator` (server-side `page` / `per_page`).
- Columns: Query Text, Search Volume, Difficulty, Opportunity Score, Visibility, Action.
- Filters: min score via `mat-slider` (→ `min_score`), visibility via `mat-select`
  (→ `status=visible|not_visible|unknown`). Changing a filter resets to page 1.
- Opportunity Score chip: green ≥ 0.7, yellow 0.4–0.69, red < 0.4.
- "Recheck" per row → `POST /api/v1/queries/{uuid}/recheck` → replace that row with the
  response; per-row loading; snackbar "recheck done" or error.

### 5. Opportunity Score Chart (tab)
- Bar chart (ng2-charts or ngx-charts) of opportunity score per query.
- X-axis: query text truncated to 30 chars. Y-axis: opportunity score fixed to 0–1.
- Bar colour: domain visible = blue, not visible = orange.
- Lives as a tab on Profile Detail.

### 6. Recommendations (tab)
- `mat-card` layout, not a table.
- Each card: Title, Content Type badge, Priority badge (colour-coded), Rationale,
  Keywords (chips).
- Filter via `mat-button-toggle-group`: All / High / Medium / Low.
- Empty state: illustration + message when no recommendations exist (Material ships no
  illustrations — confirm the equivalent, e.g. a large `mat-icon`).

## Lazy loading with tabs
The spec requires lazy-loaded Dashboard, Profiles, and Queries routes while Queries,
Chart and Recommendations appear as tabs on Profile Detail. Confirm with the user how tabs
map to routes (e.g. child routes under the profile) before building the routing.

## Done check per view
- [ ] Data via a service, typed interface, no mock data
- [ ] Loading, error (user-friendly), empty states
- [ ] Required snackbars fire
- [ ] Works at 1280px and 768px
