# Database Optimization

## Connection pooling (applied)
`app/db/session.py`: async engine with `pool_size`, `max_overflow`,
`pool_pre_ping`, `pool_recycle=1800`. Tune `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`
to `(replicas × pool_size) < max_connections`.

## Statement timeout (applied)
PostgreSQL `statement_timeout` is set from `DB_STATEMENT_TIMEOUT_MS` (default
30s) via asyncpg `server_settings`, bounding runaway queries.

## Slow query logging (applied)
A SQLAlchemy `before/after_cursor_execute` listener logs `slow_query` (with
duration + truncated statement) when a statement exceeds `DB_SLOW_QUERY_MS`
(default 500ms).

## Indexes (existing)
Indexed columns already cover the hot paths, e.g.:
- `collected_articles`: `source_id`, `url` (unique), `published_date`, `status`,
  `content_hash`, `overall_relevance_score`, `ranking_position`, `is_selected`,
  `verification_status`, `category_id`, `newsletter_section`
- `newsletters.issue_number` (unique), `newsletters.status`
- `review_sessions`: `newsletter_id`, `review_status`, `review_state`
- `publication_records`: `newsletter_id`, `channel`, `publication_status`,
  `publish_state`
- `agent_runs`: `agent_name`, `execution_status`, `workflow_run_id`
- unique constraints: `subscribers.email`, `users.email`,
  `newsletter_versions(newsletter_id, version_number)`

## Recommended composite indexes (add as volume grows)
```sql
CREATE INDEX ix_articles_status_published   ON collected_articles (status, published_date DESC);
CREATE INDEX ix_articles_selected_rank      ON collected_articles (is_selected, ranking_position);
CREATE INDEX ix_pub_records_newsletter_chan ON publication_records (newsletter_id, channel);
CREATE INDEX ix_agent_runs_wf_status        ON agent_runs (workflow_run_id, execution_status);
CREATE INDEX ix_analytics_newsletter_chan   ON publication_analytics (newsletter_id, channel);
```
Add these in a new Alembic migration when query plans show seq scans on these
predicates.

## Query optimization recommendations
- Use the read replica for analytics/history endpoints (`GET /api/publications`,
  stats) to keep the primary write-focused.
- **Partition** `collected_articles`, `agent_runs`, `publication_analytics` by
  month/quarter once they pass ~10M rows; archive cold partitions.
- Always paginate list endpoints (already `limit/offset`); prefer keyset
  pagination for deep history.
- Avoid N+1: relationships use `lazy="selectin"`; load only what's needed.
- `VACUUM (ANALYZE)` / autovacuum tuning on the high-churn tables.
