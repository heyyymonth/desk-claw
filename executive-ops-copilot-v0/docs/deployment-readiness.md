# Deployment Readiness Checklist

This checklist tracks the repo-side and outside-infrastructure work needed before Desk AI can be hosted publicly on a hyperscaler.

## Current Status

| Area | Status | Evidence |
| --- | --- | --- |
| CI test gates | Complete | Backend lint/tests, frontend lint/tests/build, and browser E2E run on pushes and pull requests. |
| Container publishing | Complete | CI publishes backend and frontend images to GHCR with `latest` and `git-<sha>` tags. |
| Parallel image builds | Complete | Backend and frontend image builds run as separate CI jobs after the shared gates pass. |
| Kubernetes image wiring | Complete | `infra/k8s/kustomization.yaml` maps workload placeholders to published GHCR images. |
| Container image access | Complete | `docs/deployment-image-access.md` documents public vs private GHCR access; `infra/k8s-overlays/private-ghcr` and `scripts/create-ghcr-pull-secret.sh` support private package pulls. |
| Runtime secret contract | Complete | `desk-ai-secrets` is documented and wired into backend pods without committing real values. |
| Public entry point | Complete | Frontend is exposed through Ingress; backend remains private behind the frontend `/api` proxy. |
| Kubernetes manifest validation | Complete | CI runs `scripts/validate-k8s.sh` to render kustomize, run offline schema validation, and check deployment invariants. |
| Immutable release render path | Complete | `scripts/render-release-k8s.sh` renders production manifests with backend and frontend pinned to the same `git-<sha>` image tag. |
| Deployed smoke test | Complete | `scripts/smoke-deploy.sh` checks the public frontend root, `/api/health`, default rules, and mock calendar through ingress. |
| Resource tuning guidance | Complete | `docs/deployment-resource-tuning.md` documents Ollama/backend CPU, memory, GPU, and timeout sizing guidance. |
| Rollout and rollback runbook | Complete | `docs/deployment-rollout-runbook.md` documents commit-tag promotion, `kubectl rollout status`, smoke verification, and rollback paths. |
| Network policy baseline | Complete | `infra/k8s/network-policy.yaml` isolates backend and Ollama ingress while `docs/deployment-network-policy.md` captures CNI and ingress-controller hardening steps. |
| NetworkPolicy enforcement release path | Complete | `REQUIRE_NETWORK_POLICY_ENFORCEMENT=true`, `FRONTEND_INGRESS_POLICY=enabled`, and `scripts/check-network-policy.sh` support CNI evidence checks and frontend ingress isolation once ingress-controller labels are known. |
| Database migration path | Complete | `docs/deployment-database-migration.md` documents the SQLite-to-managed-Postgres path and CI enforces one backend replica while SQLite is configured. |
| PVC backup and restore runbook | Complete | `docs/deployment-backup-restore.md` documents backend SQLite backups, restore flow, provider snapshots, and Ollama data recovery. |
| Production auth/session design | Complete | `docs/deployment-auth-session.md` defines OIDC/session/RBAC target state and CI validates public frontend image builds do not bundle admin or actor secrets. |
| Runtime observability exports | Complete | `GET /metrics` exports backend health, model warmup, AI latency, ADK coverage, tool failure, and telemetry scrape-health metrics; `docs/deployment-observability.md` documents ingress-controller error monitoring. |
| Provider selection guide | Complete | `docs/deployment-provider-selection.md` captures the EKS/GKE/AKS decision, required cluster capabilities, first-cluster shape, and follow-on deployment work. |
| Domain and DNS release path | Complete | `docs/deployment-domain-dns.md` documents public host selection, release-time Ingress host rendering, DNS record setup, and `scripts/check-public-dns.sh` verification. |
| TLS issuing path | Complete | `docs/deployment-tls.md` documents cert-manager, pre-created Secret, and provider-managed certificate modes; `scripts/render-cert-manager-issuer.sh` and `scripts/check-public-tls.sh` support issuance and verification. |
| Secret management release path | Complete | `docs/deployment-secret-management.md` documents External Secrets and manual fallback paths; `scripts/render-external-secret.sh`, `scripts/check-runtime-secret.sh`, and `REQUIRE_RUNTIME_SECRET=true` support production verification. |
| Model hosting release path | Complete | `docs/deployment-model-hosting.md` documents CPU, NVIDIA GPU, and external private model modes; `infra/k8s-overlays/ollama-gpu-nvidia`, `infra/k8s-overlays/external-model`, `MODEL_ENDPOINT_URL`, and `scripts/check-model-runtime.sh` support release-time verification. |
| Persistent storage release path | Complete | `docs/deployment-storage-policy.md` documents StorageClass and VolumeSnapshotClass selection; `STORAGE_CLASS_NAME`, PVC backup annotations, `scripts/check-storage-policy.sh`, and `scripts/render-volume-snapshot.sh` support production verification. |
| Public access controls release path | Complete | `docs/deployment-public-access.md` documents IP allowlist and provider-gated modes; `REQUIRE_PUBLIC_ACCESS_CONTROL=true`, `PUBLIC_ACCESS_MODE`, and `scripts/check-public-access.sh` support release-time verification. |
| Local container stack | Present | Docker Compose starts Ollama, backend, and frontend for local validation. |

## Issues Found While Preparing Deployment

| Finding | Impact | Resolution |
| --- | --- | --- |
| Image builds were serialized in one CI job. | Slow deploy feedback and no independent image build visibility. | Split into `Backend container image` and `Frontend container image` jobs. |
| Kubernetes manifests used `ghcr.io/OWNER/...` placeholders. | Applying manifests directly would fail to pull application images. | Added kustomize image mappings to the published `heyyymonth` GHCR images. |
| Private GHCR image pulls had no repo-supported deployment path. | A production cluster could stall in `ImagePullBackOff` or require undocumented manual patches. | Added a private GHCR overlay, pull-secret helper, release-renderer support, and validation for both public and private image-pull paths. |
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
| Ingress host replacement was a manual YAML edit. | A production release could accidentally keep the placeholder host or drift from the immutable release manifest. | Added `PUBLIC_HOST` and `TLS_SECRET_NAME` release-render inputs, DNS-specific manifest validation, and a live ingress DNS verification script. |
| TLS was hardcoded to cert-manager without an issuer setup path. | Clusters using provider-managed certs or pre-created TLS Secrets could retain a stale cert-manager annotation, and cert-manager clusters had no repeatable ClusterIssuer render. | Added `TLS_MODE`, `TLS_CLUSTER_ISSUER`, cert-manager ClusterIssuer rendering, and public TLS verification. |
| Runtime secrets were optional in every manifest render. | Public backend pods could start without admin/actor secret material, leaving operators with a silent auth mismatch. | Added `REQUIRE_RUNTIME_SECRET=true`, ExternalSecret rendering, and a runtime Secret checker that validates Secret contents and backend deployment wiring. |
| Model hosting was implicit and base-only. | Operators could accidentally expose a CPU-only Ollama pod to broad traffic, hand-edit GPU settings, or leave an external model endpoint undocumented. | Added explicit CPU, NVIDIA GPU, and external private model release paths, manifest validation for each mode, and a model runtime checker tied to `/api/health`. |
| PVC storage class selection was implicit. | Production could bind SQLite and model-cache data to an unsuitable default StorageClass with unknown expansion, reclaim, or snapshot behavior. | Added release-time StorageClass pinning, PVC backup annotations, storage policy verification, and VolumeSnapshot rendering. |
| Public ingress access controls were only an owner decision. | A release could become publicly reachable without an allowlist, WAF/DDoS record, or identity-provider decision. | Added explicit `ip-allowlist` and `provider-gated` public access modes, ingress annotations, renderer validation, and a deployed Ingress checker. |
| NetworkPolicy enforcement depended on an undocumented cluster check. | A cluster could accept NetworkPolicy objects without an enforcing CNI, or frontend isolation could use mismatched ingress-controller labels and break public traffic. | Added release-time CNI confirmation metadata, optional rendered `frontend-ingress` policy, manifest validation, and `scripts/check-network-policy.sh` for live policy/CNI verification. |

## Remaining Repo Work

No blocking repo-side deployment readiness items remain in this checklist. The remaining work is environment-specific and listed under outside-repo dependencies.

## Outside-Repo Dependencies

| Dependency | Owner Decision Needed |
| --- | --- |
| Hyperscaler and Kubernetes flavor | Choose EKS, GKE, AKS, or another managed Kubernetes option using `docs/deployment-provider-selection.md`. |
| Container image access | Choose public GHCR packages or private GHCR credentials using `docs/deployment-image-access.md`. |
| Domain and DNS | Choose the public hostname and create the DNS record using `docs/deployment-domain-dns.md`; verify with `scripts/check-public-dns.sh`. |
| TLS issuing path | Choose cert-manager, provider-managed certificates, or a manually created TLS Secret using `docs/deployment-tls.md`; verify with `scripts/check-public-tls.sh`. |
| Secret management | Use provider secret manager or External Secrets to create `desk-ai-secrets` using `docs/deployment-secret-management.md`; verify with `scripts/check-runtime-secret.sh`. |
| Model hosting shape | Choose one supported path from `docs/deployment-model-hosting.md`: base in-cluster CPU, `infra/k8s-overlays/ollama-gpu-nvidia`, or `infra/k8s-overlays/external-model` with `MODEL_ENDPOINT_URL`; use the composed private-GHCR overlays when package access is private. |
| Persistent storage class | Choose the provider StorageClass and optional VolumeSnapshotClass using `docs/deployment-storage-policy.md`; render releases with `STORAGE_CLASS_NAME` and verify with `scripts/check-storage-policy.sh`. |
| Public access controls | Choose `ip-allowlist` or `provider-gated` mode using `docs/deployment-public-access.md`; verify with `scripts/check-public-access.sh`. |
| NetworkPolicy enforcement | Choose/confirm the enforcing CNI, identify ingress-controller namespace/pod labels, render with `REQUIRE_NETWORK_POLICY_ENFORCEMENT=true` and `FRONTEND_INGRESS_POLICY=enabled`, then verify with `scripts/check-network-policy.sh`. |
| Managed Postgres | Choose provider, region, network path, backup/PITR policy, and secret-management integration before backend horizontal scaling. |
| Storage backup mechanism | Choose CSI snapshots, provider disk snapshots, or an external backup tool and confirm restore support for the selected storage class. |
| Identity provider | Choose OIDC/SAML provider, required claims, role mapping, session store, and signout behavior before public admin access. |
| Observability stack | Choose Prometheus/Grafana, managed Prometheus, or another metrics backend; confirm ingress-controller metrics are enabled and map alerts to the selected ingress implementation. |

## Deployment Gate

Do not treat the system as public-production ready until these are true:

- CI is green on the commit being deployed.
- The deployed images use immutable `git-<sha>` tags.
- The release manifest is rendered with the real `PUBLIC_HOST` and `TLS_SECRET_NAME`; the rendered Ingress no longer contains `desk-ai.example.com`.
- The selected GHCR access path is verified: public packages pull anonymously, or `desk-ai/ghcr-pull-secret` exists and the private overlay is used.
- Rollout status and rollback commands are known to the operator before promotion.
- The ingress hostname, TLS path, and DNS are real, not placeholders, and `scripts/check-public-dns.sh` passes.
- Public access controls are explicit in the release render, and `scripts/check-public-access.sh` passes against the deployed Ingress.
- The TLS mode is explicit in the release render and `scripts/check-public-tls.sh` passes against the public hostname.
- Runtime secrets come from a secret manager or out-of-band Kubernetes Secret, the release is rendered with `REQUIRE_RUNTIME_SECRET=true`, and `scripts/check-runtime-secret.sh` passes.
- The cluster CNI is confirmed to enforce NetworkPolicy, `frontend-ingress` isolation is rendered with the real ingress-controller selector, and `scripts/check-network-policy.sh` passes.
- Admin dashboard access is protected by real login/session auth, not frontend-bundled keys, and production auth has passed the deployment auth/session gate.
- Backend `/metrics` and ingress-controller metrics are scraped by the selected observability stack, with alerts for backend/model readiness, AI latency, tool failures, telemetry scrape errors, and ingress 4xx/5xx rates.
- Backend persistence remains one replica on SQLite, or Postgres support has been implemented and cut over through the database migration runbook.
- PVC backups and at least one restore drill have succeeded, or managed storage backup/PITR has replaced the PVC recovery path.
- The selected StorageClass is pinned in the release manifest, the selected VolumeSnapshotClass exists if snapshots are required, and `scripts/check-storage-policy.sh` passes.
- The selected model-hosting mode is explicit, Ollama capacity or private endpoint capacity is sized, and `scripts/check-model-runtime.sh` passes after rollout.
- A post-deploy smoke test passes through the public ingress.
