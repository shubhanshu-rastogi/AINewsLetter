# Performance Report

Generated with `scripts/load_test.py` against a single local Uvicorn worker
backed by **SQLite** (dev harness — not the production Postgres). Numbers are
indicative of relative behavior, not production capacity.

## Environment
- 1 Uvicorn worker, 1 event loop, full middleware stack enabled
- SQLite (single file; serializes writes), rate limiting disabled for the test
- Host: developer laptop

## Results

| Scenario | Requests | OK | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|---|
| Health load (500 concurrent) | 500 | 500 | 167 rps | 2207 ms | 2566 ms | 2600 ms |
| Newsletter generation (conc 25) | 20 | 2 | 78 rps | 184 ms | 254 ms | 254 ms |
| Subscriber requests (conc 50) | 200 | 200 | 283 rps | 125 ms | 331 ms | 631 ms |

## Interpretation
- **Health @ 500 concurrent**: ~167 rps sustained on a *single* worker; high p50
  is queueing on one event loop. Horizontal scaling (replicas × workers behind
  the LB) is the lever — the app is stateless, so this scales near-linearly.
- **Subscriber writes**: ~283 rps, p50 125 ms — healthy even on SQLite.
- **Newsletter generation**: 18/20 failed under concurrency. **Root cause: a
  race on `newsletters.issue_number`** — concurrent generations read the same
  `max(issue_number)` and collide on the unique constraint. This is a
  correctness limitation of the writer under parallel generation, not a hardening
  defect. Newsletter generation is a weekly, low-concurrency operation, so it is
  low-risk in practice. **Recommended fix:** allocate `issue_number` from a
  Postgres sequence (or retry-on-conflict), tracked separately.

## Production capacity guidance
- Run Uvicorn with `--workers N` (≈ CPU cores) per container, and multiple
  replicas behind the LB. Health/read traffic scales horizontally.
- Postgres (vs SQLite) removes the write-serialization ceiling seen here.
- Long-running agent workflows should execute in a background worker pool, not
  in the request path, so API latency stays flat under load.

## Re-running
```bash
# point the app at a DB, start it, then:
python -m scripts.load_test --base-url http://localhost:8000 \
    --users 500 --newsletters 100 --subscribers 1000 --reviews 100
```
