# Agent pipeline & data flow (as-built)

These diagrams reflect the **implemented** system in `app/workflows/` and
`app/agents/` — generated from [`graph.py`](../app/workflows/graph.py),
[`routing.py`](../app/workflows/routing.py), and
[`nodes.py`](../app/workflows/nodes.py).

> The diagrams in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) (§2 component,
> §3 agent-interaction) are the original **design-time** sketches and have
> drifted from the build (they reference pgvector, a Postgres checkpointer,
> Celery workers, S3, and a memory service that were not implemented). Use the
> diagrams below as the source of truth for how the system actually runs.

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
