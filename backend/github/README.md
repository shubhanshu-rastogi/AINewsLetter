# GitHub Actions

The CI pipeline lives at the **repository root** so GitHub executes it:
`.github/workflows/ci.yml` (working directory `backend/`).

Jobs: `lint`, `typecheck` (advisory), `test` (coverage ≥ 90%), `migrations`,
`security` (advisory), `docker-build`. See `docs/cicd.md` for the full matrix,
gates, and local pre-push commands.
