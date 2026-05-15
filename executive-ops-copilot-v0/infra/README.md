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
Deployment readiness tracking lives in `../docs/deployment-readiness.md`.
Resource and timeout tuning guidance lives in `../docs/deployment-resource-tuning.md`.

## Container Images

The CI workflow builds backend and frontend container images in separate parallel jobs after lint, tests, build, and E2E pass.
Pull requests build the images without publishing them. Pushes to `main` publish:

```text
ghcr.io/heyyymonth/desk-ai-backend:latest
ghcr.io/heyyymonth/desk-ai-backend:git-<sha>
ghcr.io/heyyymonth/desk-ai-frontend:latest
ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>
```

For a public cluster, make those GHCR packages public or configure Kubernetes image pull credentials.

Create the backend runtime secret before enabling admin telemetry or trusted actor attribution:

```bash
cp infra/k8s/secrets.example.yaml infra/k8s/secrets.yaml
```

Edit `infra/k8s/secrets.yaml` with real generated values, then apply it out of band:

```bash
kubectl apply -f infra/k8s/secrets.yaml
```

The real `secrets.yaml` file is ignored by git. On a hyperscaler, prefer the provider secret manager or External Secrets and make it create a Kubernetes Secret named `desk-ai-secrets` in the `desk-ai` namespace. The backend reads `ADMIN_API_KEY` and `ACTOR_AUTH_TOKEN` from that Secret when present; without it, admin read endpoints fail closed and trusted actor headers stay disabled.

The default kustomization maps the workload placeholders to the published GHCR images:

```text
ghcr.io/heyyymonth/desk-ai-backend:latest
ghcr.io/heyyymonth/desk-ai-frontend:latest
```

Apply the stack:

```bash
kubectl apply -k infra/k8s
```

## Public Entry Point

The default Kubernetes path exposes only the frontend through an Ingress. The backend remains a private ClusterIP service and is reached through the frontend nginx `/api` proxy.

Before a public deployment, update `infra/k8s/ingress.yaml` for your environment:

```yaml
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - desk-ai.example.com
      secretName: desk-ai-tls
  rules:
    - host: desk-ai.example.com
```

Production dependencies outside this repo:

- an ingress controller installed in the cluster, such as nginx ingress or a hyperscaler-managed ingress controller;
- DNS pointing the chosen host to the ingress controller load balancer;
- TLS issued by cert-manager, provider-managed certificates, or a pre-created `desk-ai-tls` Secret;
- provider firewall/security-group rules allowing public HTTPS traffic to the ingress controller.

For production rollouts, prefer immutable commit tags over `latest`. Render a release manifest with the CI commit tag, then apply the rendered output:

```bash
./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
```

The release renderer creates a temporary kustomize overlay, sets backend and frontend images to the same immutable `git-<sha>` tag, and leaves the base manifests on `latest` for local/default use.

Recommended rollout order for first deployment:

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai wait --for=condition=available deployment/ollama --timeout=300s
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

Do not apply raw `backend.yaml` or `frontend.yaml` directly for production releases; the published image tags are applied through kustomize and the release renderer.

The backend readiness probe depends on `/api/health`, which only reports ready after startup model warmup succeeds.

After DNS and TLS are active, run the public smoke test against the real ingress host:

```bash
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

The smoke test calls the frontend root and deterministic backend endpoints through the same public origin. It does not call live LLM generation paths.

## Resource Tuning

The checked-in Kubernetes resources are an internal pilot baseline:

- backend: `250m` CPU and `512Mi` memory requests, with `2` CPU and `2Gi` memory limits;
- Ollama: `1` CPU and `8Gi` memory requests, with `4` CPU and `16Gi` memory limits;
- frontend: `100m` CPU and `128Mi` memory requests, with `500m` CPU and `512Mi` memory limits.

For public exposure, review `../docs/deployment-resource-tuning.md` before choosing node shapes. The most important decisions are whether Ollama runs CPU-only or on a GPU node, whether `gemma4:latest` fits in usable VRAM with runtime/cache overhead, and whether `OLLAMA_WARMUP_TIMEOUT_SECONDS` and `ADK_AGENT_TIMEOUT_SECONDS` match observed cold-load and agent-loop latency.

## Operational Notes

- SQLite is mounted on a `ReadWriteOnce` PVC and the backend defaults to one replica. Move to Postgres before scaling backend replicas horizontally.
- Ollama model storage is mounted on a PVC so the model pull survives pod restarts.
- Do not ship `VITE_ADMIN_API_KEY` or `VITE_ACTOR_AUTH_TOKEN` in public frontend builds. Those Vite variables are only for local V0 inspection until real login/session auth replaces the admin key path.
- The frontend nginx proxy assumes the backend service name is `backend` in the same namespace.
- The checked-in ingress host is a placeholder; replace `desk-ai.example.com` before public DNS cutover.
