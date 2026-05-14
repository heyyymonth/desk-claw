# Infrastructure

This directory contains deployment prep for running Desk AI as separate services:

- `backend`: FastAPI orchestration, ADK agents, SQLite audit storage.
- `frontend`: React/Vite app served by nginx, with `/api` proxied to backend.
- `ollama`: local model runtime for `gemma4:latest`.

## Local Containers

From `executive-ops-copilot-v0/`:

```bash
docker compose up --build
```

The compose stack starts Ollama, pulls `gemma4:latest`, starts the backend after the model is available, and serves the frontend at:

```text
http://localhost:5173
```

Backend health:

```bash
curl http://localhost:8000/api/health
```

## Kubernetes

Kubernetes manifests live in `infra/k8s/`.

## Container Images

The CI workflow builds backend and frontend container images after lint, tests, build, and E2E pass.
Pull requests build the images without publishing them. Pushes to `main` publish:

```text
ghcr.io/heyyymonth/desk-ai-backend:latest
ghcr.io/heyyymonth/desk-ai-backend:git-<sha>
ghcr.io/heyyymonth/desk-ai-frontend:latest
ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>
```

For a public cluster, make those GHCR packages public or configure Kubernetes image pull credentials.

Before applying them to a real cluster, replace the placeholder images:

```text
ghcr.io/OWNER/desk-ai-backend:latest
ghcr.io/OWNER/desk-ai-frontend:latest
```

Apply the stack:

```bash
kubectl apply -k infra/k8s
```

Recommended rollout order for first deployment:

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai wait --for=condition=available deployment/ollama --timeout=300s
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
kubectl apply -f infra/k8s/backend.yaml
kubectl apply -f infra/k8s/frontend.yaml
```

The backend readiness probe depends on `/api/health`, which only reports ready after startup model warmup succeeds.

## Operational Notes

- SQLite is mounted on a `ReadWriteOnce` PVC and the backend defaults to one replica. Move to Postgres before scaling backend replicas horizontally.
- Ollama model storage is mounted on a PVC so the model pull survives pod restarts.
- `ADMIN_API_KEY` and `ACTOR_AUTH_TOKEN` should be supplied as Kubernetes Secrets before enabling protected admin or actor-auth flows in production.
- The frontend nginx proxy assumes the backend service name is `backend` in the same namespace.
