# System architecture, agent pipeline & data flow (as-built)

These diagrams reflect the **implemented** system across `frontend/`,
`app/api/`, `app/workflows/`, and `app/agents/` — generated from the actual code
([`graph.py`](../app/workflows/graph.py), [`routing.py`](../app/workflows/routing.py),
[`nodes.py`](../app/workflows/nodes.py), [`service.py`](../app/workflows/service.py),
and the API routers).

> The diagrams in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) (§2 component,
> §3 agent-interaction) are the original **design-time** sketches and have
> drifted from the build (they reference pgvector, a Postgres checkpointer,
> Celery workers, S3, and a memory service that were not implemented). Use the
> diagrams below as the source of truth for how the system actually runs.

## System architecture (full stack)

The operator console (a React + Vite SPA) talks to the FastAPI backend over
REST. The API exposes auth, runtime configuration, workflow control, and the
per-issue HTML page. Workflow runs execute in the background; the UI polls for
live stage progress. Configuration set in the UI is encrypted at rest and
applied to the live settings the agents read.

```mermaid
flowchart TB
    subgraph Browser["Operator console — React + Vite SPA"]
      UI1[Dashboard: trigger runs]
      UI2[Run detail: live progress + review]
      UI3[History + per-issue web-page links]
      UI4[Settings: keys, models, flags]
      UI5[Login: admin token]
    end

    Browser -->|"REST + Bearer token"| API

    subgraph API["FastAPI — REST API"]
      A1["/api/auth — config / login / verify"]
      A2["/api/settings — read / update config"]
      A3["/api/workflows — start, status, list, review"]
      A4["/api/newsletters — drafts + {id}/html"]
      A5["/api/publish · /api/subscribers · /health · /metrics"]
    end

    A2 <--> RC[runtime config service]
    RC <-->|"encrypted secrets"| SS[("system_settings")]
    RC -. applies at runtime .-> CFG[live settings]

    A3 --> WS["workflow service<br/>background runs + progress<br/>MemorySaver checkpointer"]
    WS --> GRAPH["LangGraph — 12 agents"]
    UI2 -. polls /status .-> A3

    GRAPH --> DB[("PostgreSQL")]
    GRAPH --> FS[("local file storage")]
    A4 --> DB
    GRAPH --> PUB[publisher]
    PUB -. when ENABLE_REAL_PUBLISHING .-> EXT["Beehiiv / LinkedIn / email"]
    CFG -. read by .-> GRAPH
```

**Key points (matching the code):**

- The SPA ([`frontend/`](../../frontend/)) is the primary interface; everything
  it does is also available directly over the REST API.
- `start` returns immediately and the run executes in the background; the UI
  polls `/api/workflows/{id}/status` for `run_state`, `progress_percent`, and the
  per-stage stepper.
- Auth is a single admin token (`REVIEW_AUTH_TOKEN`); when set, the `workflows`,
  `settings`, `publish`, and `subscribers` routes require it.
- UI-managed config is persisted to `system_settings` (secrets encrypted with a
  key derived from `SECRET_KEY`) and applied to the live `settings` object on
  save and on startup, so agents pick up keys/flags without an `.env` edit.
- Each issue has a self-contained HTML page at `/api/newsletters/{id}/html`
  (public), rendered from the stored draft — works even in simulated mode.

## How the agents connect

The newsletter is produced by a LangGraph state machine. Every hop is a
conditional edge, so any node failure diverts to the error handler. The graph
is compiled with `interrupt_after=[human_review]`, so it physically pauses after
human review and resumes when a review decision is posted.

```mermaid
flowchart TD
    START([weekly schedule / API trigger]) --> SC[source collection]
    SC --> RF[relevance filter]
    RF --> CAT[categorization]
    CAT --> FC[fact-check]
    FC --> NW[newsletter writer]
    NW --> LI[linkedin writer]
    LI --> VIS[visual generation]
    VIS --> ED[editorial review]
    ED -->|editorial_passed| HR[/human review — PAUSE/]
    ED -->|QA failed| DR[draft regeneration]
    HR --> AR{approval router}
    AR -->|approved| PUB[publisher]
    AR -->|feedback_required| FB[feedback processor]
    AR -->|rejected| DONE([completion])
    FB --> DR
    DR --> ED
    PUB --> DONE

    SC -. failure .-> ERR[error handler]
    RF -. failure .-> ERR
    CAT -. failure .-> ERR
    FC -. failure .-> ERR
    NW -. failure .-> ERR
    LI -. failure .-> ERR
    VIS -. failure .-> ERR
    ED -. failure .-> ERR
    ERR --> END([end])
```

**Key points (matching the code):**

- `editorial_review` is an **automated** QA pass. `route_editorial` sends a
  passing draft to `human_review`, a failing one to `draft_regeneration`.
- `human_review` is the **only** interrupt point. The run is checkpointed and
  the worker is released; nothing is held in memory waiting.
- `route_approval` branches on the reviewer's decision: `approved → publisher`,
  `feedback_required → feedback_processor`, `rejected → completion`.
- The feedback loop is `feedback_processor → draft_regeneration →
  editorial_review`, so a revised draft is re-reviewed before publishing.
- The newsletter writer is the content hub; `linkedin_writer` and
  `visual_generation` build on its draft.

## How data flows through the system

State is persisted in PostgreSQL between steps (the LangGraph checkpointer keeps
run state; the agents read/write domain tables). Generated image files are
written to local storage; publishing writes records and analytics back to the
database.

```mermaid
flowchart LR
    subgraph SRC[content sources]
      RSS[RSS feeds]
      RES[research sites]
      NLS[newsletters]
      DOC[vendor docs]
    end

    SRC --> SC[source collection]
    SC -->|raw articles| DB[(PostgreSQL)]
    DB --> PIPE[relevance → categorization → fact-check]
    PIPE -->|scored, categorized, vetted| DB
    DB --> GEN[writer + linkedin + visuals]
    GEN -->|newsletter, post, image metadata| DB
    GEN -->|cover & carousel files| FS[(local file storage)]
    DB --> REV[editorial + human review]
    REV -->|approved draft| PUBA[publisher]
    PUBA --> BEE[Beehiiv]
    PUBA --> LNK[LinkedIn]
    PUBA --> EML[email package]
    PUBA -->|publication records + analytics| DB
```

When `ENABLE_REAL_PUBLISHING` is off (default), the Beehiiv / LinkedIn / email
steps are simulated — records are written but no external calls are made.
