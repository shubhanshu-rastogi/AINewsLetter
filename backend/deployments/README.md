# Deployments

Deployment targets and procedures live in `docs/deployment.md`.

- **Single server / Docker Compose**: use `../docker-compose.prod.yml`.
- **Future Kubernetes**: the API is stateless with `livenessProbe=/health/live`
  and `readinessProbe=/health/ready`; the scheduler runs as a single-replica
  leader; background execution as a worker Deployment. Manifests/Helm are
  intentionally not included (out of scope) — add them here when adopting k8s.
