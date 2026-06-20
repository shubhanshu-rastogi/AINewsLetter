# Dependency & Static Scanning

CI runs these as advisory jobs (`.github/workflows/ci.yml` → `security`).

## Dependency CVEs — pip-audit
```bash
pip install pip-audit
pip-audit -r requirements.txt
pip-audit -r requirements-dev.txt
```

## Static analysis — bandit
```bash
pip install bandit
bandit -r app -x app/agents      # agents are heuristic/text code; focus on core/api
```

## Policy
- Triage HIGH/CRITICAL findings within one sprint.
- Pin/upgrade vulnerable transitive deps; document accepted risks here.
- Promote these jobs to **blocking** once the baseline is clean.
