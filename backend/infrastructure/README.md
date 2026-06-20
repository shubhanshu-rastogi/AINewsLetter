# Infrastructure

Infrastructure-as-Code (Terraform/Pulumi) is not included in this phase. When
adopting it, provision:

- Managed PostgreSQL (with PITR), managed Redis
- Object storage bucket for visual assets (`AssetStorage` S3 backend)
- Secret manager entries for all keys in `.env.production`
- Container registry + runtime (ECS/GKE/AKS or a VM with Docker Compose)
- Prometheus/Grafana (or a managed equivalent) scraping `/metrics`

Runtime config and scaling guidance: `docs/architecture_production.md`,
`docs/deployment.md`.
