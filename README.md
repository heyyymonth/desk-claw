# Desk Claw

Lightweight agentic request parser for incoming scheduling and operational text.

The runnable app lives in `executive-ops-copilot-v0/`. See that README for local setup, API shape, and deployment notes.

Deployment layers:

- Docker Compose: local development and container smoke testing.
- GitHub Actions: CI checks, separate container builds, container smoke, and tag-only GHCR publishing.
- Kubernetes: production-style orchestration in `infra/k8s/`.

Apply the Kubernetes manifests from the repo root:

```bash
kubectl apply -k infra/k8s
```
