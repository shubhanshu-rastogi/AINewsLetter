# Security Policy

## Reporting a vulnerability
Email security@aiqeweekly.example.com with details and reproduction steps. Do
not open public issues for vulnerabilities. We aim to acknowledge within 2
business days.

## Scope
- Backend API (`backend/app`)
- Deployment configuration (`docker-compose*.yml`, env templates)

## Controls (see `docs/security.md` for detail)
- Security headers, CORS allow-list, request size limit, rate limiting, idempotency
- Pydantic input validation; SQLAlchemy bound parameters (no string SQL)
- Secret provider abstraction; secrets masked in logs; no secrets in VCS
- Dependency + static scanning in CI (`pip-audit`, `bandit`)

## Secret rotation
Rotate provider keys (OpenAI/Anthropic/Beehiiv/LinkedIn/Notion), `SECRET_KEY`,
and DB credentials on a schedule and on suspected exposure. Because secrets are
injected at runtime, rotation is a redeploy with new values — no code change.
