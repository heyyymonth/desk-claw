# Deployment Readiness Checklist

This checklist tracks the repo-side and outside-infrastructure work needed before Desk AI can be hosted publicly on a hyperscaler.

## Current Status

| Area | Status | Evidence |
| --- | --- | --- |
| CI test gates | Complete | Backend lint/tests, frontend lint/tests/build, and browser E2E run on pushes and pull requests. |
| Container publishing | Complete | CI publishes backend and frontend images to GHCR with `latest` and `git-<sha>` tags. |
| Parallel image builds | Complete | Backend and frontend image builds run as separate CI jobs after the shared gates pass. |
| Kubernetes image wiring | Complete | `infra/k8s/kustomization.yaml` maps workload placeholders to published GHCR images. |
| Runtime secret contract | Complete | `desk-ai-secrets` is documented and wired into backend pods without committing real values. |
| Public entry point | Complete | Frontend is exposed through Ingress; backend remains private behind the frontend `/api` proxy. |
| Kubernetes manifest validation | Complete | CI runs `scripts/validate-k8s.sh` to render kustomize, run offline schema validation, and check deployment invariants. |
| Local container stack | Present | Docker Compose starts Ollama, backend, and frontend for local validation. |

## Issues Found While Preparing Deployment

| Finding | Impact | Resolution |
| --- | --- | --- |
| Image builds were serialized in one CI job. | Slow deploy feedback and no independent image build visibility. | Split into `Backend container image` and `Frontend container image` jobs. |
| Kubernetes manifests used `ghcr.io/OWNER/...` placeholders. | Applying manifests directly would fail to pull application images. | Added kustomize image mappings to the published `heyyymonth` GHCR images. |
| Backend admin/actor secrets had no Kubernetes contract. | Operators could enable unsafe ad hoc secrets or accidentally commit values. | Added `secrets.example.yaml`, ignored real `secrets.yaml`, and wired optional `desk-ai-secrets`. |
| Frontend was exposed directly as `LoadBalancer`. | Public access was tied to a service-level load balancer and left no TLS/host routing shape. | Moved public access to Ingress and kept frontend/backend services internal. |
| Production frontend must use same-origin `/api`. | A public browser cannot call `hostname:8000` directly. | CI builds the frontend with empty `VITE_API_BASE_URL`, so nginx proxies `/api` to the backend service. Do not set `VITE_API_BASE_URL` for public builds unless intentionally routing to a separate API origin. |
| `kubectl apply --dry-run=client` tried API discovery in CI. | A runner without a cluster failed against `localhost:8080`, even for client dry-run. | CI now renders manifests with `kubectl kustomize`, parses the YAML stream, validates schemas with kubeconform, and checks repo-specific invariants offline. |
| Local Docker credential helper may be missing. | Local image build can fail before reaching Dockerfile logic. | CI build is authoritative; local workaround is to use a clean `DOCKER_CONFIG` or repair Docker Desktop credentials. |

## Remaining Repo Work

1. Add a production overlay or release patch path for immutable image tags so deploys can use `git-<sha>` without editing the base manually.
2. Add a smoke-test script for a deployed environment: health, frontend root, `/api/health` through ingress, and one deterministic backend workflow call.
3. Add resource tuning documentation for Ollama and backend timeouts, including expected CPU, memory, and GPU needs.
4. Add rollout and rollback commands using `kubectl rollout status`, `kubectl rollout undo`, and commit-tag image promotion.
5. Add network policy manifests after the target ingress controller and cluster CNI are known.
6. Add database migration path from single-replica SQLite PVC to managed Postgres before horizontal backend scaling.
7. Add backup/restore guidance for persistent volumes until managed storage replaces them.
8. Add production auth/session design before exposing admin dashboards to real users.
9. Add runtime observability exports for backend health, AI telemetry, tool failures, model latency, and ingress errors.

## Outside-Repo Dependencies

| Dependency | Owner Decision Needed |
| --- | --- |
| Hyperscaler and Kubernetes flavor | Choose EKS, GKE, AKS, or another managed Kubernetes option. |
| Container image access | Make GHCR packages public or configure cluster image pull credentials. |
| Domain and DNS | Choose the public hostname and point DNS to the ingress load balancer. |
| TLS issuing path | Use cert-manager, provider-managed certificates, or a manually created TLS Secret. |
| Secret management | Use provider secret manager or External Secrets to create `desk-ai-secrets`. |
| Model hosting shape | Decide whether Ollama runs in-cluster, on GPU nodes, or behind a separate private model endpoint. |
| Persistent storage class | Choose the PVC storage class and backup policy for Ollama model data and backend data. |
| Public access controls | Decide IP allowlists, WAF, DDoS protection, and identity provider before broad exposure. |

## Deployment Gate

Do not treat the system as public-production ready until these are true:

- CI is green on the commit being deployed.
- The deployed images use immutable `git-<sha>` tags.
- The ingress hostname, TLS path, and DNS are real, not placeholders.
- Runtime secrets come from a secret manager or out-of-band Kubernetes Secret.
- Admin dashboard access is protected by real login/session auth, not frontend-bundled keys.
- Backend persistence has a production plan, either managed Postgres or an explicit single-replica SQLite limitation.
- Ollama capacity is sized and model warmup succeeds before backend readiness.
- A post-deploy smoke test passes through the public ingress.
