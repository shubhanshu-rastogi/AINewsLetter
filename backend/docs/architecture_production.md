# Production Architecture

```mermaid
flowchart TB
    subgraph edge[Edge]
        LB[Load Balancer / TLS termination]
    end

    subgraph app[Application tier - stateless, horizontally scaled]
        API1[FastAPI replica 1]
        API2[FastAPI replica 2]
        SCHED[APScheduler\n(single leader)]
    end

    subgraph data[Data tier]
        PG[(PostgreSQL\nprimary + read replicas)]
        REDIS[(Redis\ncache / locks / rate limit)]
        OBJ[(Object storage\nvisual assets)]
    end

    subgraph obs[Observability]
        PROM[Prometheus]
        GRAF[Grafana]
        OTEL[OTLP collector\n(optional)]
    end

    subgraph ext[External APIs]
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        BEEHIIV[Beehiiv]
        LINKEDIN[LinkedIn]
        NOTION[Notion]
    end

    LB --> API1 & API2
    API1 & API2 --> PG
    API1 & API2 --> REDIS
    API1 & API2 --> OBJ
    SCHED --> PG
    API1 & API2 -->|/metrics| PROM
    PROM --> GRAF
    API1 & API2 -.->|traces| OTEL
    API1 & API2 --> OPENAI & ANTHROPIC & BEEHIIV & LINKEDIN & NOTION
```

## Component responsibilities

| Layer | Component | Notes |
|---|---|---|
| Edge | Load balancer | TLS, routing, health-check based pool membership (`/health/ready`) |
| App | FastAPI replicas | Stateless; scale horizontally. Middleware: request-id, CORS, security headers, metrics, rate-limit, idempotency, size-limit |
| App | APScheduler | Run as a **single** leader (one replica or a dedicated worker) to avoid duplicate weekly runs |
| Data | PostgreSQL | Primary for writes; read replicas for analytics/history. Pooling + statement timeout |
| Data | Redis | Rate-limit counters, idempotency cache, locks, retry coordination. Optional in dev (in-memory fallback) |
| Data | Object storage | Generated visual assets (`storage/` locally; S3 via the `AssetStorage` abstraction) |
| Obs | Prometheus + Grafana | Scrape `/metrics`; dashboards for app/workflow/newsletter/publication/infra |
| Obs | OTLP collector | Optional traces (`ENABLE_TRACING=true`) |

## Scaling to the target volumes

- **100k+ articles / 10k+ newsletters / 1M+ agent runs / multi-year history** — time-partition the high-volume tables (`collected_articles`, `agent_runs`, `publication_analytics`) by month/quarter; move analytics reads to a replica; archive cold partitions.
- **Horizontal scaling** — API is stateless. The only single-instance concern is the LangGraph in-process `MemorySaver` checkpointer and APScheduler; in production use the **Postgres LangGraph checkpointer** and a single scheduler leader so any replica can resume a paused workflow.
- **Long-running workflows** — execution belongs in a background worker pool; the API only triggers and resumes. Human-review pauses are durable in Postgres, so they survive restarts.
