# CI/CD

Pipeline: `.github/workflows/ci.yml` (repo root), runs on push/PR to `main`,
working directory `backend/`, Python 3.12, `APP_ENV=test`.

## Jobs
| Job | Gate | What it does |
|---|---|---|
| `lint` | **blocking** | `ruff check` + `ruff format --check` (ruff supersedes black/isort, avoiding tool conflicts) |
| `typecheck` | advisory | `mypy app` (continue-on-error: dynamic langgraph/sqlalchemy typing friction) |
| `test` | **blocking** | `pytest --cov=app --cov-fail-under=90` + coverage XML artifact |
| `migrations` | **blocking** | `alembic upgrade head` → `alembic check` (no drift) → `alembic downgrade base` on SQLite |
| `security` | advisory | `pip-audit` (deps) + `bandit` (static) |
| `docker-build` | **blocking** | builds the production image (needs lint+test+migrations) |

## Quality gates
- Tests must pass.
- **Coverage ≥ 90%** (`--cov-fail-under=90`; the suite currently sits at ~92%).
- Migrations must apply, be drift-free, and reverse.
- Lint + format must be clean.
- Typing is advisory (see note); tighten incrementally toward blocking.

## PR checks
`lint` (format + lint), `typecheck`, `test` (+coverage threshold), `migrations`.

## Local pre-push
```bash
ruff check app tests scripts && ruff format --check app tests scripts
pytest --cov=app --cov-fail-under=90
ALEMBIC_DATABASE_URL=sqlite:///ci.db alembic upgrade head && alembic check
```

## Notes
- **black/isort**: the spec lists them; we standardize on **ruff** which
  implements both an Black-compatible formatter (`ruff format`) and import
  sorting (rule `I`). Running ruff + black together would conflict, so ruff is
  the single source of truth. `[tool.black]`/`[tool.isort]` configs are kept
  (black/isort profile = ruff settings) for teams that prefer the standalone tools.
- **mypy** is advisory because LangGraph's `add_node` overloads and SQLAlchemy
  `Result.rowcount` produce false positives; promote to blocking after stubbing.
