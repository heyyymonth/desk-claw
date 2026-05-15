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
| Immutable release render path | Complete | `scripts/render-release-k8s.sh` renders production manifests with backend and frontend pinned to the same `git-<sha>` image tag. |
| Deployed smoke test | Complete | `scripts/smoke-deploy.sh` checks the public frontend root, `/api/health`, default rules, and mock calendar through ingress. |
| Resource tuning guidance | Complete | `docs/deployment-resource-tuning.md` documents Ollama/backend CPU, memory, GPU, and timeout sizing guidance. |
| Rollout and rollback runbook | Complete | `docs/deployment-rollout-runbook.md` documents commit-tag promotion, `kubectl rollout status`, smoke verification, and rollback paths. |
| Network policy baseline | Complete | `infra/k8s/network-policy.yaml` isolates backend and Ollama ingress while `docs/deployment-network-policy.md` captures CNI and ingress-controller hardening steps. |
| Database migration path | Complete | `docs/deployment-database-migration.md` documents the SQLite-to-managed-Postgres path and CI enforces one backend replica while SQLite is configured. |
| PVC backup and restore runbook | Complete | `docs/deployment-backup-restore.md` documents backend SQLite backups, restore flow, provider snapshots, and Ollama data recovery. |
| Production auth/session design | Complete | `docs/deployment-auth-session.md` defines OIDC/session/RBAC target state and CI validates public frontend image builds do not bundle admin or actor secrets. |
| Runtime observability exports | Complete | `GET /metrics` exports backend health, model warmup, AI latency, ADK coverage, tool failure, and telemetry scrape-health metrics; `docs/deployment-observability.md` documents ingress-controller error monitoring. |
| Provider selection guide | Complete | `docs/deployment-provider-selection.md` captures the EKS/GKE/AKS decision, required cluster capabilities, first-cluster shape, and follow-on deployment work. |
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
| Ollama resource expectations were implicit. | Clusters could be under-sized, causing cold-start delays, request timeouts, or `OOMKilled` pods. | Added resource tuning guidance and raised the checked-in Ollama memory baseline for `gemma4:latest`. |
| Rollout and rollback steps were spread across docs. | Operators could apply a release without waiting for readiness or could roll back inconsistently. | Added a dedicated rollout runbook with commit-tag promotion, status checks, smoke tests, and rollback guidance. |
| Internal service traffic was not isolated in Kubernetes. | Any pod in an enforcing cluster could attempt direct backend or Ollama access. | Added baseline NetworkPolicies for backend and Ollama ingress and documented provider-specific frontend/egress hardening. |
| SQLite scaling risk was documented only as a note. | Backend replicas could be raised against a `ReadWriteOnce` SQLite PVC, risking write contention and data corruption. | Added a managed Postgres migration path and a manifest validation guard that fails when SQLite is configured with more than one backend replica. |
| PVCs had no recovery procedure. | A disk, namespace, or cluster failure could lose SQLite audit/decision data or force slow model repulls. | Added backup/restore guidance for `backend-data` and `ollama-data`, including SQLite integrity checks and provider snapshot guidance. |
| Admin access still used local V0 keys. | Browser-bundled admin keys or actor tokens would expose audit and telemetry access in a public deployment. | Added a production auth/session design and a CI guard against shipping `VITE_ADMIN_API_KEY` or `VITE_ACTOR_AUTH_TOKEN` in the public frontend image. |
| Runtime telemetry was visible only through app endpoints and docs. | Operators lacked a scrapeable signal path for backend/model readiness, AI tool failures, latency, and ingress errors. | Added a sanitized Prometheus text export, backend scrape metadata, monitoring NetworkPolicy allowance, and ingress-controller metric guidance. |
| Hyperscaler choice was an open owner decision with no decision record. | Deployment could drift into an under-specified cluster choice without checking NetworkPolicy, storage, model hosting, auth, or observability needs. | Added a provider selection guide with major-provider fit, required capabilities, a recommended first path, and a decision template. |

## Remaining Repo Work

No blocking repo-side deployment readiness items remain in this checklist. The remaining work is environment-specific and listed under outside-repo dependencies.

## Outside-Repo Dependencies

| Dependency | Owner Decision Needed |
| --- | --- |
| Hyperscaler and Kubernetes flavor | Choose EKS, GKE, AKS, or another managed Kubernetes option using `docs/deployment-provider-selection.md`. |
| Container image access | Make GHCR packages public or configure cluster image pull credentials. |
| Domain and DNS | Choose the public hostname and point DNS to the ingress load balancer. |
| TLS issuing path | Use cert-manager, provider-managed certificates, or a manually created TLS Secret. |
| Secret management | Use provider secret manager or External Secrets to create `desk-ai-secrets`. |
| Model hosting shape | Decide whether Ollama runs in-cluster, on GPU nodes, or behind a separate private model endpoint. |
| Persistent storage class | Choose the PVC storage class and backup policy for Ollama model data and backend data. |
| Public access controls | Decide IP allowlists, WAF, DDoS protection, and identity provider before broad exposure. |
| NetworkPolicy enforcement | Confirm the cluster CNI enforces NetworkPolicy and identify ingress-controller namespace/pod labels before frontend ingress isolation. |
| Managed Postgres | Choose provider, region, network path, backup/PITR policy, and secret-management integration before backend horizontal scaling. |
| Storage backup mechanism | Choose CSI snapshots, provider disk snapshots, or an external backup tool and confirm restore support for the selected storage class. |
| Identity provider | Choose OIDC/SAML provider, required claims, role mapping, session store, and signout behavior before public admin access. |
| Observability stack | Choose Prometheus/Grafana, managed Prometheus, or another metrics backend; confirm ingress-controller metrics are enabled and map alerts to the selected ingress implementation. |

## Deployment Gate

Do not treat the system as public-production ready until these are true:

- CI is green on the commit being deployed.
- The deployed images use immutable `git-<sha>` tags.
- Rollout status and rollback commands are known to the operator before promotion.
- The ingress hostname, TLS path, and DNS are real, not placeholders.
- Runtime secrets come from a secret manager or out-of-band Kubernetes Secret.
- The cluster CNI is confirmed to enforce NetworkPolicy, or traffic isolation is handled by another provider control.
- Admin dashboard access is protected by real login/session auth, not frontend-bundled keys, and production auth has passed the deployment auth/session gate.
- Backend `/metrics` and ingress-controller metrics are scraped by the selected observability stack, with alerts for backend/model readiness, AI latency, tool failures, telemetry scrape errors, and ingress 4xx/5xx rates.
- Backend persistence remains one replica on SQLite, or Postgres support has been implemented and cut over through the database migration runbook.
- PVC backups and at least one restore drill have succeeded, or managed storage backup/PITR has replaced the PVC recovery path.
- Ollama capacity is sized and model warmup succeeds before backend readiness.
- A post-deploy smoke test passes through the public ingress.
