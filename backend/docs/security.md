# Security

## HTTP hardening (middleware)
- **Security headers** (`SecurityHeadersMiddleware`): `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `X-XSS-Protection`,
  `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`,
  `Permissions-Policy`, and HSTS in staging/production.
- **CORS** (`CORSMiddleware`): origins from `CORS_ORIGINS` (comma-separated).
  Production validation rejects the `*` wildcard.
- **Request size limit** (`RequestSizeLimitMiddleware`): rejects bodies over
  `MAX_REQUEST_BYTES` (default 2 MB) with `413`.
- **Rate limiting** (`RateLimitMiddleware`): fixed-window per client+group on
  `/api/reviews`, `/api/publish`, `/api/publications`, `/api/subscribers`;
  returns `429` + `Retry-After`.
- **Idempotency** (`IdempotencyMiddleware`): `Idempotency-Key` on mutating
  protected requests prevents duplicate publications/resumes/reviews/retries.

## Input validation & injection
- All request bodies are validated by Pydantic schemas (typed, constrained).
- **SQL injection**: SQLAlchemy Core/ORM with bound parameters everywhere — no
  string-built SQL.
- **XSS**: API returns JSON (no server-rendered HTML). The email HTML builder
  (`email_preparer`) escapes all interpolated values with `html.escape`.

## Secrets
- Read via `app/core/secrets.py` `SecretProvider` (env now; pluggable manager
  later). Never committed — `.env` is gitignored; `.env.staging/production` are
  secret-free templates.
- Logs mask secret-shaped values; `mask_secret()` / `mask_text()` helpers.

## Authentication (placeholder)
`app/core/auth.py` defines a swappable `AuthProvider` (default permissive;
`JWTAuthProvider` stub for future JWT/OAuth/SSO). Review endpoints currently use
the interim `require_reviewer` bearer-token gate (`REVIEW_AUTH_TOKEN`).
**Publish/subscriber endpoints are not yet authenticated — add `require_reviewer`/RBAC before production.**

## CSRF strategy
The API is token/stateless (no session cookies), so traditional CSRF does not
apply. If a cookie-based browser session is added later: use `SameSite=Lax`
(or `Strict`), `Secure`, `HttpOnly` cookies and a double-submit CSRF token on
state-changing requests.

## Secure cookies (when introduced)
`Secure`, `HttpOnly`, `SameSite=Lax`, scoped `Path`/`Domain`, short TTL.

## Dependency vulnerability scanning
CI runs `pip-audit` (deps) and `bandit` (static) as advisory jobs. Run locally:
```bash
pip install pip-audit bandit
pip-audit -r requirements.txt
bandit -r app -x app/agents
```
See `security/SECURITY.md` for the disclosure policy.
