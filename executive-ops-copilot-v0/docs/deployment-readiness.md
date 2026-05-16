# Deployment Readiness Checklist

This checklist tracks the repo-side and outside-infrastructure work needed before Desk AI can be hosted publicly on a hyperscaler.

## Current Status

This checklist uses separate evidence stages so repo readiness is not confused with a production-proven deployment:

- `Done`: implemented or verified for that evidence stage.
- `Partial`: useful coverage exists, but the stage is not fully closed.
- `Pending`: still requires a real environment, owner decision, or live drill.
- `N/A`: not applicable for that area.

| Area | Repo implemented | CI/local verified | Live cluster verified | Production proven | Evidence / remaining proof |
| --- | --- | --- | --- | --- | --- |
| CI test gates | Done | Done | N/A | Done for latest `main` | Backend lint/tests, frontend lint/tests/build, browser E2E, Postgres integration, Kubernetes manifests, and image jobs pass on pushes. |
| Container publishing | Done | Done | Pending | Pending | CI publishes backend and frontend images to GHCR with `latest` and `git-<sha>` tags; next proof is pulling selected tags from the target cluster. |
| Parallel image builds | Done | Done | N/A | Done | Backend and frontend image builds run as separate CI jobs after shared gates pass. |
| Kubernetes image wiring | Done | Done | Pending | Pending | `infra/k8s/kustomization.yaml` maps workload placeholders to published GHCR images; next proof is deployed pods running immutable `git-<sha>` images. |
| Container image access | Done | Done | Pending | Pending | Public/private GHCR paths are documented and rendered; target cluster must prove anonymous pull or `desk-ai/ghcr-pull-secret` access. |
| Runtime secret contract | Done | Done | Pending | Pending | `desk-ai-secrets` is documented, rendered, and checked; target cluster must prove ExternalSecret/manual Secret readiness and rotation procedure. |
| Public entry point | Done | Done | Pending | Pending | Frontend Ingress is rendered and backend stays private by manifest/checker; target cluster must prove ingress controller, DNS, TLS, and exposure checks. |
| Kubernetes manifest validation | Done | Done | Pending | Pending | CI renders kustomize, validates schemas with kubeconform, and checks repo invariants; live proof is applying the rendered release to the selected cluster. |
| Immutable release render path | Done | Done | Pending | Pending | `scripts/render-release-k8s.sh` pins backend and frontend to the same `git-<sha>` tag; live proof is promotion using the rendered manifest. |
| Deployed smoke test | Done | Partial | Pending | Pending | `scripts/smoke-deploy.sh` exists; it must pass against the real public ingress after rollout. |
| Resource tuning guidance | Done | N/A | Pending | Pending | Ollama/backend CPU, memory, GPU, and timeout guidance exists; proof requires observed load, warmup, and latency data on chosen node shapes. |
| Rollout and rollback runbook | Done | Partial | Pending | Pending | Runbook exists; production proof requires at least one non-production rollout and rollback drill. |
| Network policy baseline | Done | Done | Pending | Pending | Baseline policies render and validate; target cluster must prove the selected CNI enforces NetworkPolicy. |
| NetworkPolicy enforcement release path | Done | Done | Pending | Pending | Release metadata, frontend ingress isolation, and `scripts/check-network-policy.sh` exist; live proof needs real ingress-controller labels and CNI evidence. |
| Managed Postgres release path | Done | Done | Pending | Pending | Backend supports SQLite/Postgres and CI runs live Postgres integration; production proof needs managed Postgres provisioning, migration, PITR, and canary. |
| PVC backup and restore runbook | Done | Done | Pending | Pending | Backup/restore docs and `scripts/check-sqlite-backup.sh` exist; proof requires off-cluster backup storage and a restore drill. |
| Production auth/session design | Partial | Partial | Pending | Pending | OIDC/session/RBAC design exists and CI blocks frontend-bundled admin secrets; implementation is still required before broad public admin access. |
| Runtime observability exports | Done | Done | Pending | Pending | `/metrics` and docs exist; production proof needs a selected metrics backend, scrape config, dashboards, and alerts. |
| Provider selection guide | Done | N/A | Pending | Pending | Provider decision guide exists; owner must choose hyperscaler/Kubernetes flavor and record the decision. |
| Domain and DNS release path | Done | Done | Pending | Pending | Host rendering and `scripts/check-public-dns.sh` exist; proof requires a real domain and DNS record pointing to the live ingress target. |
| GitHub Pages preview path | Done | Partial | Pending | N/A for primary product | Manual Pages workflow exists for static preview; it requires a separately secured public backend API and is not the production app hosting path. |
| TLS issuing path | Done | Done | Pending | Pending | Cert-manager/pre-created/provider-managed paths and `scripts/check-public-tls.sh` exist; proof requires real certificate issuance and renewal path. |
| Secret management release path | Done | Done | Pending | Pending | ExternalSecret/manual fallback, renderers, and live check scripts exist; proof requires provider secret manager or manual Secret in target namespace. |
| Model hosting release path | Done | Done | Pending | Pending | CPU/GPU/external modes and `scripts/check-model-runtime.sh` exist; proof requires selected model runtime capacity and live warm model checks. |
| Persistent storage release path | Done | Done | Pending | Pending | StorageClass, VolumeSnapshotClass, PVC, and SQLite backup checks exist; proof requires real StorageClass/snapshot class and restore evidence. |
| Public access controls release path | Done | Done | Pending | Pending | `ip-allowlist`/`provider-gated` modes and exposure checks exist; proof requires real ingress/WAF/DDoS/identity or allowlist evidence. |
| Local container stack | Done | Partial | N/A | N/A | Docker Compose supports local validation; it is not a substitute for live Kubernetes proof. |

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
| Backend persistence was SQLite-only. | Managed Postgres could not be used even after the external database was provisioned, blocking backend horizontal scaling. | Added a shared SQLite/Postgres database layer, Postgres `jsonb` schema support, CI Postgres integration tests, Secret-based `DATABASE_URL` release rendering, and runtime verification. |
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
| GitHub Pages was considered as a public entry point. | Pages can host static frontend files but cannot run the backend, model runtime, database, or nginx `/api` proxy needed by the full product. | Added a manual Pages preview workflow and documented it as a split-origin preview that requires a separate secured public backend API. |

## Remaining Repo Work

No blocking repo-side deployment scaffolding items remain in this checklist. The repo now has supported render, validation, and verification paths for each deployment concern.

| Repo Item | Status | Why It Remains |
| --- | --- | --- |
| Production auth/session implementation | Pending | `docs/deployment-auth-session.md` is a design and guardrail, not the implemented OIDC/session/RBAC flow required for broad public admin access. |
| Live release rehearsal wrapper | Pending | The individual scripts are present, but a single repeatable "fresh cluster from GHCR images" rehearsal command would reduce operator error before the first hyperscaler rollout. |

## Outside-Repo Dependencies

| Dependency | Owner Decision Needed |
| --- | --- |
| Hyperscaler and Kubernetes flavor | Choose EKS, GKE, AKS, or another managed Kubernetes option using `docs/deployment-provider-selection.md`. |
| Container image access | Choose public GHCR packages or private GHCR credentials using `docs/deployment-image-access.md`. |
| Domain and DNS | Choose the public hostname and create the DNS record using `docs/deployment-domain-dns.md`; verify with `scripts/check-public-dns.sh`. |
| TLS issuing path | Choose cert-manager, provider-managed certificates, or a manually created TLS Secret using `docs/deployment-tls.md`; verify with `scripts/check-public-tls.sh`. |
| Secret management | Use provider secret manager or External Secrets to create `desk-ai-secrets` using `docs/deployment-secret-management.md`; include `DATABASE_URL` when `DATABASE_MODE=postgres`; verify with `scripts/check-runtime-secret.sh` and `scripts/check-database-runtime.sh`. |
| Model hosting shape | Choose one supported path from `docs/deployment-model-hosting.md`: base in-cluster CPU, `infra/k8s-overlays/ollama-gpu-nvidia`, or `infra/k8s-overlays/external-model` with `MODEL_ENDPOINT_URL`; use the composed private-GHCR overlays when package access is private. |
| Persistent storage class | Choose the provider StorageClass and optional VolumeSnapshotClass using `docs/deployment-storage-policy.md`; render releases with `STORAGE_CLASS_NAME` and verify with `DATABASE_MODE=<mode> scripts/check-storage-policy.sh`. |
| Public access controls | Choose `ip-allowlist` or `provider-gated` mode using `docs/deployment-public-access.md`; verify with `scripts/check-public-access.sh`. |
| NetworkPolicy enforcement | Choose/confirm the enforcing CNI, identify ingress-controller namespace/pod labels, render with `REQUIRE_NETWORK_POLICY_ENFORCEMENT=true` and `FRONTEND_INGRESS_POLICY=enabled`, then verify with `scripts/check-network-policy.sh`. |
| Managed Postgres | Choose provider, region, private network path, backup/PITR policy, production `DATABASE_URL` secret, migration window, and canary plan before backend horizontal scaling. |
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
- Backend persistence remains one replica on SQLite, or the release is rendered with `DATABASE_MODE=postgres`, `scripts/check-database-runtime.sh` passes, and the Postgres canary has accepted and read back workflow/audit data.
- PVC backups and at least one restore drill have succeeded, or managed storage backup/PITR has replaced the PVC recovery path.
- The selected StorageClass is pinned in the release manifest, the selected VolumeSnapshotClass exists if snapshots are required, and `DATABASE_MODE=<mode> scripts/check-storage-policy.sh` passes.
- The selected model-hosting mode is explicit, Ollama capacity or private endpoint capacity is sized, and `scripts/check-model-runtime.sh` passes after rollout.
- A post-deploy smoke test passes through the public ingress.
