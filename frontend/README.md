# AI Visibility Intelligence — Frontend

Angular 21 dashboard for the AI Visibility Intelligence API. The full project
documentation (architecture, agents, scoring formula, design decisions) is in
[`../backend/README.md`](../backend/README.md).

## Stack

* Angular 21 (standalone components, Signals, strict TypeScript, lazy-loaded routes)
* Angular Material 21 (M3 theme)
* RxJS for HTTP, debounced filters and pipeline polling
* ng2-charts 10 / Chart.js 4 for the opportunity score chart
* Karma + Jasmine for unit tests
* `@angular/animations` for route transitions; a toolbar toggle switches the Material light/dark theme

## Setup

Requirements: Node.js 20.19+ / 22.12+ / 24 (developed on Node 24) and the backend running on
http://localhost:5000 (see the backend README).

```bash
cd frontend
npm install
npx ng serve            # or: ng serve, with the Angular CLI installed globally
```

Open http://localhost:4200.

> The assessment brief says `ng install && ng serve`. `ng install` is not an Angular CLI
> command; dependencies are installed with `npm install`.

With Docker, `docker compose up --build` from the repository root builds this app and
serves it with nginx on http://localhost:4200.

## API URL

The API base URL lives in `src/environments/`:

```ts
// src/environments/environment.ts
export const environment = {
  production: false,
  apiUrl: 'http://localhost:5000'
};
```

`environment.prod.ts` (used by `ng build`) has the same shape. The URL is read by the browser,
so it must be reachable from the user's machine; the default works for both `ng serve` and
Docker Compose because the API port is published on `localhost:5000`.

## Scripts

| Command | What it does |
|---------|--------------|
| `npx ng serve` | Dev server with live reload on port 4200. |
| `npx ng build` | Production build into `dist/frontend/browser`. |
| `npx ng test --watch=false --browsers=ChromeHeadless` | Runs the 16 unit tests once. |

## Screens and routes

| Route | Screen |
|-------|--------|
| `/` | **Dashboard**: total profiles, total queries discovered, average opportunity score, recent pipeline runs, profile list. |
| `/profiles/new` | **Business Profile Form**: reactive form with domain and competitor validation (chip input, max 10). |
| `/profiles/:profileUuid` | **Profile Detail**: profile info, Run Pipeline button with live progress (polls every 2 s), last run summary, and three tabs: |
| `…/queries` | **Queries Table**: sorted by score, filters (minimum score slider, visibility status), server-side pagination, colour-coded score chips, per-row Recheck, Export CSV (current filters). |
| `…/chart` | **Opportunity Score Chart**: bar chart per query, coloured by visibility, full query text in the tooltip. |
| `…/recommendations` | **Recommendations**: cards with content type, priority badge, rationale and keyword chips; filter by priority. |

Every screen has a skeleton loader on first load, an error state (with retry) and an empty
state, and every value shown comes from the API (no mock data). The toolbar moon/sun button
switches dark mode and remembers the choice. Changing page or profile tab fades the new view in.

## Structure

```
src/
  environments/          apiUrl per build configuration
  styles.scss            Material theme, status colours, shared page/state classes
  app/
    app.config.ts        router (component input binding), HttpClient, snackbar defaults
    app.routes.ts        lazy loadComponent routes, profile child tabs
    core/animations/     route fade (skipped when the OS requests reduced motion)
    core/services/       profile · query · pipeline · csv-export · theme · api-error
    shared/models/       typed interfaces mirroring the API JSON
    shared/components/   score-chip · skeleton
    features/
      dashboard/
      profiles/          profile-form · profile-detail
      queries/           queries-table · opportunity-chart
      recommendations/   recommendations-list
```

`PipelineService` exposes `lastFinishedRun` as a Signal; the tab components watch it and
reload their data as soon as a run for their profile finishes.
