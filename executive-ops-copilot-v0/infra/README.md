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

Backend Prometheus metrics:

```bash
curl http://localhost:8000/metrics
```

## Kubernetes

Kubernetes manifests live in `infra/k8s/`.
Deployment readiness tracking lives in `../docs/deployment-readiness.md`.
Provider selection guidance lives in `../docs/deployment-provider-selection.md`.
Container image access guidance lives in `../docs/deployment-image-access.md`.
Domain and DNS guidance lives in `../docs/deployment-domain-dns.md`.
TLS issuing guidance lives in `../docs/deployment-tls.md`.
Secret management guidance lives in `../docs/deployment-secret-management.md`.
Resource and timeout tuning guidance lives in `../docs/deployment-resource-tuning.md`.
Rollout and rollback commands live in `../docs/deployment-rollout-runbook.md`.
Network policy guidance lives in `../docs/deployment-network-policy.md`.
Database migration guidance lives in `../docs/deployment-database-migration.md`.
Backup and restore guidance lives in `../docs/deployment-backup-restore.md`.
Production auth/session guidance lives in `../docs/deployment-auth-session.md`.
Runtime observability guidance lives in `../docs/deployment-observability.md`.

## Container Images

The CI workflow builds backend and frontend container images in separate parallel jobs after lint, tests, build, and E2E pass.
Pull requests build the images without publishing them. Pushes to `main` publish:

```text
ghcr.io/heyyymonth/desk-ai-backend:latest
ghcr.io/heyyymonth/desk-ai-backend:git-<sha>
ghcr.io/heyyymonth/desk-ai-frontend:latest
ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>
```

For a public cluster, make those GHCR packages public or configure Kubernetes image pull credentials. The private package path uses the `infra/k8s-overlays/private-ghcr` overlay and a pull Secret named `ghcr-pull-secret`; see `../docs/deployment-image-access.md`.

Create private GHCR pull credentials when packages are private:

```bash
export GHCR_USERNAME=<github-username>
export GHCR_TOKEN=<classic-pat-with-read-packages>
./scripts/create-ghcr-pull-secret.sh
```

For a public cluster, create `desk-ai-secrets` from a provider secret manager or External Secrets before applying a production release:

```bash
SECRET_STORE_NAME=desk-ai-runtime-secrets REMOTE_SECRET_KEY=desk-ai/production/runtime ./scripts/render-external-secret.sh /tmp/desk-ai-external-secret.yaml
kubectl apply -f /tmp/desk-ai-external-secret.yaml
```

For a local/private manual fallback only, copy the example, replace every value, and apply the ignored file out of band:

```bash
cp infra/k8s/secrets.example.yaml infra/k8s/secrets.yaml
kubectl apply -f infra/k8s/secrets.yaml
```

The real `secrets.yaml` file is ignored by git. On a hyperscaler, prefer the provider secret manager or External Secrets and make it create a Kubernetes Secret named `desk-ai-secrets` in the `desk-ai` namespace. The backend reads `ADMIN_API_KEY` and `ACTOR_AUTH_TOKEN` from that Secret. Public releases should be rendered with `REQUIRE_RUNTIME_SECRET=true`; without that flag, the local/default manifest keeps the Secret optional and admin read endpoints fail closed when the key is absent.

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

The checked-in Ingress host is a placeholder. For production, set the public host, TLS Secret, and TLS mode while rendering the immutable release manifest rather than editing the base Ingress file:

```bash
TLS_MODE=cert-manager TLS_CLUSTER_ISSUER=letsencrypt-prod PUBLIC_HOST=desk-ai.example.com TLS_SECRET_NAME=desk-ai-tls ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

Production dependencies outside this repo:

- an ingress controller installed in the cluster, such as nginx ingress or a hyperscaler-managed ingress controller;
- DNS pointing the chosen host to the ingress controller load balancer;
- TLS issued by cert-manager, provider-managed certificates, or a pre-created `desk-ai-tls` Secret using `../docs/deployment-tls.md`;
- provider firewall/security-group rules allowing public HTTPS traffic to the ingress controller.

For production rollouts, prefer immutable commit tags over `latest`. Render a release manifest with the CI commit tag, then apply the rendered output:

```bash
REQUIRE_RUNTIME_SECRET=true RUNTIME_SECRET_NAME=desk-ai-secrets TLS_MODE=cert-manager TLS_CLUSTER_ISSUER=letsencrypt-prod PUBLIC_HOST=desk-ai.example.com TLS_SECRET_NAME=desk-ai-tls ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
```

For private GHCR packages, render the private image-pull overlay:

```bash
K8S_BASE_DIR=infra/k8s-overlays/private-ghcr REQUIRE_RUNTIME_SECRET=true RUNTIME_SECRET_NAME=desk-ai-secrets TLS_MODE=cert-manager TLS_CLUSTER_ISSUER=letsencrypt-prod PUBLIC_HOST=desk-ai.example.com TLS_SECRET_NAME=desk-ai-tls ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
```

The release renderer creates a temporary kustomize overlay, sets backend and frontend images to the same immutable `git-<sha>` tag, patches the public Ingress host when `PUBLIC_HOST` is set, applies the selected TLS mode, and leaves the base manifests on `latest` plus the placeholder host for local/default use.
Use `../docs/deployment-rollout-runbook.md` for the full promotion, `kubectl rollout status`, smoke-test, and rollback sequence.

Recommended rollout order for first deployment:

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai wait --for=condition=available deployment/ollama --timeout=300s
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
REQUIRE_RUNTIME_SECRET=true RUNTIME_SECRET_NAME=desk-ai-secrets TLS_MODE=cert-manager TLS_CLUSTER_ISSUER=letsencrypt-prod PUBLIC_HOST=desk-ai.example.com TLS_SECRET_NAME=desk-ai-tls ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
./scripts/check-runtime-secret.sh desk-ai-secrets
./scripts/check-public-dns.sh desk-ai.example.com
./scripts/check-public-tls.sh desk-ai.example.com
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

Do not apply raw `backend.yaml` or `frontend.yaml` directly for production releases; the published image tags are applied through kustomize and the release renderer.

The backend readiness probe depends on `/api/health`, which only reports ready after startup model warmup succeeds.

After DNS and TLS are active, run the public smoke test against the real ingress host:

```bash
./scripts/check-public-dns.sh desk-ai.example.com
./scripts/check-public-tls.sh desk-ai.example.com
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

The smoke test calls the frontend root and deterministic backend endpoints through the same public origin. It does not call live LLM generation paths.

Rollback options are documented in `../docs/deployment-rollout-runbook.md`. Prefer promoting the last known good `git-<sha>` tag. Use `kubectl rollout undo deployment/backend` and `kubectl rollout undo deployment/frontend` only for emergency rollback.

## Network Policy

The base Kubernetes manifests include `infra/k8s/network-policy.yaml`. The baseline allows only frontend pods to reach backend on port `8000`, and only backend plus the model-pull job to reach Ollama on port `11434`.
It also allows Prometheus pods in a `monitoring` namespace with label `app.kubernetes.io/name=prometheus` to scrape backend metrics on port `8000`.

The frontend is not ingress-isolated in the base manifest because ingress-controller namespace and pod labels are provider-specific. Review `../docs/deployment-network-policy.md` before adding frontend ingress restrictions or egress default-deny rules.

## Observability

The backend Service is annotated for Prometheus-compatible scraping at `/metrics`. The metrics export covers backend health, model warmup readiness, AI success and ADK coverage, model latency, tool failures, and telemetry scrape errors.

Ingress errors are observed from the ingress controller metrics, not from the backend pod. Review `../docs/deployment-observability.md` before production cutover so 4xx/5xx rate and ingress latency alerts match the selected ingress controller or hyperscaler load balancer.

## Resource Tuning

The checked-in Kubernetes resources are an internal pilot baseline:

- backend: `250m` CPU and `512Mi` memory requests, with `2` CPU and `2Gi` memory limits;
- Ollama: `1` CPU and `8Gi` memory requests, with `4` CPU and `16Gi` memory limits;
- frontend: `100m` CPU and `128Mi` memory requests, with `500m` CPU and `512Mi` memory limits.

For public exposure, review `../docs/deployment-resource-tuning.md` before choosing node shapes. The most important decisions are whether Ollama runs CPU-only or on a GPU node, whether `gemma4:latest` fits in usable VRAM with runtime/cache overhead, and whether `OLLAMA_WARMUP_TIMEOUT_SECONDS` and `ADK_AGENT_TIMEOUT_SECONDS` match observed cold-load and agent-loop latency.

## Operational Notes

- SQLite is mounted on a `ReadWriteOnce` PVC and the backend defaults to one replica. Move to managed Postgres before scaling backend replicas horizontally; see `../docs/deployment-database-migration.md`.
- Back up `backend-data` before releases, migrations, and storage changes. Use `../docs/deployment-backup-restore.md` until managed Postgres backup/PITR replaces SQLite backups.
- Ollama model storage is mounted on a PVC so the model pull survives pod restarts. Treat `ollama-data` as recreatable model cache unless recovery time requires provider snapshots.
- Do not ship `VITE_ADMIN_API_KEY` or `VITE_ACTOR_AUTH_TOKEN` in public frontend builds. CI validates this for the public frontend image. Those Vite variables are only for local V0 inspection until real login/session auth replaces the admin key path; see `../docs/deployment-auth-session.md`.
- The frontend nginx proxy assumes the backend service name is `backend` in the same namespace.
- The checked-in ingress host is a placeholder; set `PUBLIC_HOST` during release rendering before public DNS cutover.
