# Deployment Rollout Runbook

This runbook defines how to promote, verify, and roll back a Desk AI Kubernetes release. It assumes the public deployment path uses immutable `git-<sha>` image tags from GHCR, not mutable `latest` tags.

## Prerequisites

Before promoting a commit:

- GitHub Actions is green for the commit being deployed.
- GHCR contains both application images:
  - `ghcr.io/heyyymonth/desk-ai-backend:git-<sha>`
  - `ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>`
- Image access is decided using `docs/deployment-image-access.md`: either packages are public, or `desk-ai/ghcr-pull-secret` exists and the private GHCR overlay is used.
- `kubectl config current-context` points at the intended cluster.
- Secret management is configured using `docs/deployment-secret-management.md`, and `desk-ai-secrets` exists in the `desk-ai` namespace or is created by the configured controller.
- Public hostname, TLS Secret name, DNS owner, and ingress target are decided using `docs/deployment-domain-dns.md`.
- TLS issuing mode and issuer setup are decided using `docs/deployment-tls.md`.
- Model hosting mode is selected using `docs/deployment-model-hosting.md`.
- StorageClass, VolumeSnapshotClass, and backup policy are selected using `docs/deployment-storage-policy.md`.
- Public access mode is selected using `docs/deployment-public-access.md`.
- NetworkPolicy enforcement and ingress-controller selectors are selected using `docs/deployment-network-policy.md`.
- Any cloud firewall/security-group rules allow public HTTPS traffic to the ingress controller.
- Ollama capacity and timeout values have been reviewed against `docs/deployment-resource-tuning.md`.

Set these shell variables for the commands below:

```bash
export RELEASE_SHA=<7-40-character-git-sha>
export RELEASE_TAG="git-${RELEASE_SHA}"
export RELEASE_FILE="/tmp/desk-ai-${RELEASE_TAG}.yaml"
export PUBLIC_HOST="desk-ai.example.com"
export TLS_SECRET_NAME="desk-ai-tls"
export TLS_MODE="cert-manager"
export TLS_CLUSTER_ISSUER="letsencrypt-prod"
export RUNTIME_SECRET_NAME="desk-ai-secrets"
export MODEL_HOSTING_MODE="in-cluster"
export K8S_BASE_DIR="infra/k8s"
export MODEL_ENDPOINT_URL=""
export STORAGE_CLASS_NAME="desk-ai-retain"
export VOLUME_SNAPSHOT_CLASS_NAME="desk-ai-snapshots"
export PUBLIC_ACCESS_MODE="ip-allowlist"
export PUBLIC_ALLOWED_CIDRS="203.0.113.10/32"
export PUBLIC_WAF_POLICY_ID=""
export PUBLIC_DDOS_PROTECTION=""
export PUBLIC_IDENTITY_PROVIDER=""
export NETWORK_POLICY_PROVIDER="cilium"
export NETWORK_POLICY_ENFORCEMENT_CONFIRMED="true"
export FRONTEND_INGRESS_POLICY="enabled"
export INGRESS_CONTROLLER_NAMESPACE="ingress-nginx"
export INGRESS_CONTROLLER_POD_SELECTOR="app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller"
export PUBLIC_URL="https://${PUBLIC_HOST}"
```

Use `PUBLIC_ACCESS_MODE=provider-gated` with `PUBLIC_WAF_POLICY_ID`, `PUBLIC_DDOS_PROTECTION=true`, and `PUBLIC_IDENTITY_PROVIDER` after the provider edge controls and identity provider are configured. Keep `ip-allowlist` for private pilots or pre-auth validation.
Use `FRONTEND_INGRESS_POLICY=disabled` only while discovering the ingress-controller namespace and labels. Public releases should set it to `enabled` after the CNI has been confirmed to enforce NetworkPolicy.

Set `MODEL_HOSTING_MODE=gpu` and `K8S_BASE_DIR=infra/k8s-overlays/ollama-gpu-nvidia` for the NVIDIA GPU runtime. Set `MODEL_HOSTING_MODE=external`, `K8S_BASE_DIR=infra/k8s-overlays/external-model`, and `MODEL_ENDPOINT_URL=https://ollama.internal.example.com` for a private external Ollama-compatible endpoint. If GHCR packages are private, use `infra/k8s-overlays/private-ghcr`, `infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia`, or `infra/k8s-overlays/private-ghcr-external-model` as the selected `K8S_BASE_DIR`.

Confirm the target context before applying anything:

```bash
kubectl config current-context
kubectl get namespace desk-ai || true
kubectl -n desk-ai get deployments || true
```

## First Cluster Bootstrap

Run this once per fresh cluster or namespace. The model pull can take a long time on cold storage or CPU-only nodes.

For in-cluster CPU or GPU model hosting, bootstrap the namespace, config, Ollama runtime, and model-pull job:

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai rollout status deployment/ollama --timeout=300s

kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
```

For GPU mode, label and optionally taint the GPU node pool before applying the release overlay:

```bash
kubectl label node <gpu-node-name> desk-ai/model-runtime=ollama-gpu
kubectl taint node <gpu-node-name> desk-ai/model-runtime=ollama-gpu:NoSchedule
```

For external model mode, skip the Ollama bootstrap and verify the private model endpoint from a temporary pod or the backend pod network before promotion.

If the model changes and the job already exists, delete and recreate the job after updating the config:

```bash
kubectl -n desk-ai delete job ollama-pull-gemma4 --ignore-not-found
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
```

## Promote a Commit Tag

If this is the first cert-manager deployment in the cluster, render and apply the production ClusterIssuer after testing the staging issuer path from `docs/deployment-tls.md`:

```bash
ACME_EMAIL=ops@example.com ACME_ENV=prod ./scripts/render-cert-manager-issuer.sh "$TLS_CLUSTER_ISSUER" /tmp/desk-ai-${TLS_CLUSTER_ISSUER}.yaml
kubectl apply -f /tmp/desk-ai-${TLS_CLUSTER_ISSUER}.yaml
```

If this is the first deployment in the cluster, apply the ExternalSecret or manually created runtime Secret from `docs/deployment-secret-management.md` before rendering the application release:

```bash
SECRET_STORE_NAME=desk-ai-runtime-secrets \
  REMOTE_SECRET_KEY=desk-ai/production/runtime \
  ./scripts/render-external-secret.sh /tmp/desk-ai-external-secret.yaml
kubectl apply -f /tmp/desk-ai-external-secret.yaml
```

Render the release manifest with the immutable commit tag and selected model-hosting path:

```bash
K8S_BASE_DIR="$K8S_BASE_DIR" \
  MODEL_ENDPOINT_URL="$MODEL_ENDPOINT_URL" \
  STORAGE_CLASS_NAME="$STORAGE_CLASS_NAME" \
  REQUIRE_PUBLIC_ACCESS_CONTROL=true \
  PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" \
  PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" \
  PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" \
  PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" \
  PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" \
  REQUIRE_NETWORK_POLICY_ENFORCEMENT=true \
  NETWORK_POLICY_PROVIDER="$NETWORK_POLICY_PROVIDER" \
  NETWORK_POLICY_ENFORCEMENT_CONFIRMED="$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" \
  FRONTEND_INGRESS_POLICY="$FRONTEND_INGRESS_POLICY" \
  INGRESS_CONTROLLER_NAMESPACE="$INGRESS_CONTROLLER_NAMESPACE" \
  INGRESS_CONTROLLER_POD_SELECTOR="$INGRESS_CONTROLLER_POD_SELECTOR" \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME="$RUNTIME_SECRET_NAME" \
  TLS_MODE="$TLS_MODE" \
  TLS_CLUSTER_ISSUER="$TLS_CLUSTER_ISSUER" \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  ./scripts/render-release-k8s.sh "$RELEASE_TAG" "$RELEASE_FILE"
```

If GHCR packages are private and no model-hosting overlay is selected, render the image-pull-secret overlay:

```bash
K8S_BASE_DIR=infra/k8s-overlays/private-ghcr \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  TLS_MODE="$TLS_MODE" \
  TLS_CLUSTER_ISSUER="$TLS_CLUSTER_ISSUER" \
  MODEL_ENDPOINT_URL="$MODEL_ENDPOINT_URL" \
  STORAGE_CLASS_NAME="$STORAGE_CLASS_NAME" \
  REQUIRE_PUBLIC_ACCESS_CONTROL=true \
  PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" \
  PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" \
  PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" \
  PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" \
  PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" \
  REQUIRE_NETWORK_POLICY_ENFORCEMENT=true \
  NETWORK_POLICY_PROVIDER="$NETWORK_POLICY_PROVIDER" \
  NETWORK_POLICY_ENFORCEMENT_CONFIRMED="$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" \
  FRONTEND_INGRESS_POLICY="$FRONTEND_INGRESS_POLICY" \
  INGRESS_CONTROLLER_NAMESPACE="$INGRESS_CONTROLLER_NAMESPACE" \
  INGRESS_CONTROLLER_POD_SELECTOR="$INGRESS_CONTROLLER_POD_SELECTOR" \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME="$RUNTIME_SECRET_NAME" \
  ./scripts/render-release-k8s.sh "$RELEASE_TAG" "$RELEASE_FILE"
```

For private GHCR plus GPU or external model hosting, set `K8S_BASE_DIR` to the composed overlay before using the general render command:

```bash
export K8S_BASE_DIR=infra/k8s-overlays/private-ghcr-ollama-gpu-nvidia
# or:
export K8S_BASE_DIR=infra/k8s-overlays/private-ghcr-external-model
```

Review the application image tags before applying:

```bash
grep -E "image: ghcr.io/heyyymonth/desk-ai-(backend|frontend):" "$RELEASE_FILE"
grep -A2 "imagePullSecrets:" "$RELEASE_FILE" || true
grep -E "host:|secretName:" "$RELEASE_FILE"
grep -A4 "secretRef:" "$RELEASE_FILE"
```

Apply the release:

```bash
kubectl apply -f "$RELEASE_FILE"
```

Wait for rollout completion:

```bash
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
```

Confirm the running images:

```bash
kubectl -n desk-ai get deployment backend -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl -n desk-ai get deployment frontend -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Verify that runtime secrets exist and the backend requires them:

```bash
./scripts/check-runtime-secret.sh "$RUNTIME_SECRET_NAME"
```

Verify that the selected model runtime is warm and wired through ADK:

```bash
MODEL_HOSTING_MODE="$MODEL_HOSTING_MODE" ./scripts/check-model-runtime.sh "$PUBLIC_URL"
```

Verify StorageClass, snapshot class, PVC binding, and backup annotations:

```bash
MODEL_HOSTING_MODE="$MODEL_HOSTING_MODE" \
  VOLUME_SNAPSHOT_CLASS_NAME="$VOLUME_SNAPSHOT_CLASS_NAME" \
  REQUIRE_VOLUME_SNAPSHOT_CLASS=true \
  ./scripts/check-storage-policy.sh "$STORAGE_CLASS_NAME"
```

Verify public access controls on the deployed Ingress:

```bash
PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" \
  PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" \
  PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" \
  PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" \
  PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" \
  ./scripts/check-public-access.sh "$PUBLIC_HOST"
```

Verify NetworkPolicy resources and CNI evidence:

```bash
NETWORK_POLICY_PROVIDER="$NETWORK_POLICY_PROVIDER" \
  NETWORK_POLICY_ENFORCEMENT_CONFIRMED="$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" \
  REQUIRE_FRONTEND_INGRESS_POLICY=true \
  INGRESS_CONTROLLER_NAMESPACE="$INGRESS_CONTROLLER_NAMESPACE" \
  INGRESS_CONTROLLER_POD_SELECTOR="$INGRESS_CONTROLLER_POD_SELECTOR" \
  ./scripts/check-network-policy.sh desk-ai
```

Verify that public DNS points at the current ingress target:

```bash
./scripts/check-public-dns.sh "$PUBLIC_HOST"
```

Verify that public HTTPS serves a certificate for the selected host:

```bash
./scripts/check-public-tls.sh "$PUBLIC_HOST"
```

Run the public smoke check:

```bash
./scripts/smoke-deploy.sh "$PUBLIC_URL"
```

A release is complete only after rollout status commands, runtime-secret verification, model-runtime verification, storage-policy verification, public-access verification, NetworkPolicy verification, DNS verification, TLS verification, and the smoke test pass.

## Preferred Rollback: Promote the Last Known Good Commit

The safest rollback is another immutable release render using the last known good commit tag. This leaves a clear manifest and image-tag record.

```bash
export PREVIOUS_RELEASE_SHA=<last-known-good-git-sha>
export PREVIOUS_RELEASE_TAG="git-${PREVIOUS_RELEASE_SHA}"
export ROLLBACK_FILE="/tmp/desk-ai-${PREVIOUS_RELEASE_TAG}.yaml"

K8S_BASE_DIR="$K8S_BASE_DIR" MODEL_ENDPOINT_URL="$MODEL_ENDPOINT_URL" STORAGE_CLASS_NAME="$STORAGE_CLASS_NAME" REQUIRE_PUBLIC_ACCESS_CONTROL=true PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" REQUIRE_NETWORK_POLICY_ENFORCEMENT=true NETWORK_POLICY_PROVIDER="$NETWORK_POLICY_PROVIDER" NETWORK_POLICY_ENFORCEMENT_CONFIRMED="$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" FRONTEND_INGRESS_POLICY="$FRONTEND_INGRESS_POLICY" INGRESS_CONTROLLER_NAMESPACE="$INGRESS_CONTROLLER_NAMESPACE" INGRESS_CONTROLLER_POD_SELECTOR="$INGRESS_CONTROLLER_POD_SELECTOR" REQUIRE_RUNTIME_SECRET=true RUNTIME_SECRET_NAME="$RUNTIME_SECRET_NAME" TLS_MODE="$TLS_MODE" TLS_CLUSTER_ISSUER="$TLS_CLUSTER_ISSUER" PUBLIC_HOST="$PUBLIC_HOST" TLS_SECRET_NAME="$TLS_SECRET_NAME" ./scripts/render-release-k8s.sh "$PREVIOUS_RELEASE_TAG" "$ROLLBACK_FILE"
kubectl apply -f "$ROLLBACK_FILE"
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
./scripts/check-runtime-secret.sh "$RUNTIME_SECRET_NAME"
MODEL_HOSTING_MODE="$MODEL_HOSTING_MODE" ./scripts/check-model-runtime.sh "$PUBLIC_URL"
MODEL_HOSTING_MODE="$MODEL_HOSTING_MODE" VOLUME_SNAPSHOT_CLASS_NAME="$VOLUME_SNAPSHOT_CLASS_NAME" REQUIRE_VOLUME_SNAPSHOT_CLASS=true ./scripts/check-storage-policy.sh "$STORAGE_CLASS_NAME"
PUBLIC_ACCESS_MODE="$PUBLIC_ACCESS_MODE" PUBLIC_ALLOWED_CIDRS="$PUBLIC_ALLOWED_CIDRS" PUBLIC_WAF_POLICY_ID="$PUBLIC_WAF_POLICY_ID" PUBLIC_DDOS_PROTECTION="$PUBLIC_DDOS_PROTECTION" PUBLIC_IDENTITY_PROVIDER="$PUBLIC_IDENTITY_PROVIDER" ./scripts/check-public-access.sh "$PUBLIC_HOST"
NETWORK_POLICY_PROVIDER="$NETWORK_POLICY_PROVIDER" NETWORK_POLICY_ENFORCEMENT_CONFIRMED="$NETWORK_POLICY_ENFORCEMENT_CONFIRMED" REQUIRE_FRONTEND_INGRESS_POLICY=true INGRESS_CONTROLLER_NAMESPACE="$INGRESS_CONTROLLER_NAMESPACE" INGRESS_CONTROLLER_POD_SELECTOR="$INGRESS_CONTROLLER_POD_SELECTOR" ./scripts/check-network-policy.sh desk-ai
./scripts/check-public-dns.sh "$PUBLIC_HOST"
./scripts/check-public-tls.sh "$PUBLIC_HOST"
./scripts/smoke-deploy.sh "$PUBLIC_URL"
```

Use this path when the previous good commit is known and its GHCR images still exist.

## Emergency Rollback: Kubernetes Rollout Undo

Use `kubectl rollout undo` when the new release is actively failing and a fast rollback is more important than rendering a fresh manifest first.

Inspect rollout history:

```bash
kubectl -n desk-ai rollout history deployment/backend
kubectl -n desk-ai rollout history deployment/frontend
```

Undo both application deployments to the previous revision:

```bash
kubectl -n desk-ai rollout undo deployment/backend
kubectl -n desk-ai rollout undo deployment/frontend
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
./scripts/smoke-deploy.sh "$PUBLIC_URL"
```

To roll back to a specific revision:

```bash
kubectl -n desk-ai rollout undo deployment/backend --to-revision=<backend-revision>
kubectl -n desk-ai rollout undo deployment/frontend --to-revision=<frontend-revision>
```

After an emergency undo, render and apply the last known good commit tag as a follow-up so Git, GHCR, and Kubernetes converge on an explicit release state.

## Rollout Failure Triage

If a rollout stalls or smoke tests fail:

```bash
kubectl -n desk-ai get pods -o wide
kubectl -n desk-ai describe deployment backend
kubectl -n desk-ai describe deployment frontend
kubectl -n desk-ai logs deployment/backend --tail=200
kubectl -n desk-ai logs deployment/frontend --tail=200
kubectl -n desk-ai describe pod -l app=ollama
kubectl -n desk-ai logs deployment/ollama --tail=200
kubectl -n desk-ai get events --sort-by=.lastTimestamp | tail -40
```

Common responses:

| Symptom | Response |
| --- | --- |
| Backend rollout waits until timeout. | Check `/api/health`, Ollama readiness, model warmup fields, and backend logs. |
| Frontend rolls out but `/api` fails. | Check nginx proxy config, backend service endpoints, and same-origin ingress routing. |
| Ollama is ready but model warmup fails. | Re-run or inspect `ollama-pull-gemma4`, then check model availability inside the Ollama pod. |
| External model mode cannot warm up. | Confirm `MODEL_ENDPOINT_URL`, private DNS, firewall/security-group rules, TLS trust, and that `gemma4:latest` is available on the endpoint. |
| GPU Ollama pod is pending. | Check the NVIDIA device plugin, allocatable `nvidia.com/gpu`, `desk-ai/model-runtime=ollama-gpu` node label, and taint/toleration. |
| Storage policy check fails. | Confirm the StorageClass exists, allows expansion, PVCs are `Bound`, and the selected VolumeSnapshotClass exists if snapshots are required. |
| Public access check fails. | Confirm `PUBLIC_ACCESS_MODE`, nginx allowlist annotation, provider WAF/DDoS controls, and identity-provider decision in `docs/deployment-public-access.md`. |
| NetworkPolicy check fails. | Confirm the CNI enforces NetworkPolicy, the baseline policies exist, and `INGRESS_CONTROLLER_NAMESPACE` plus `INGRESS_CONTROLLER_POD_SELECTOR` match the actual ingress-controller pods. Disable only `FRONTEND_INGRESS_POLICY` while correcting selector mismatches. |
| Backend pod fails because `desk-ai-secrets` is missing. | Apply the ExternalSecret/manual Secret from `docs/deployment-secret-management.md`, then rerun rollout status. |
| DNS check fails. | Confirm the DNS zone, record type, and Ingress load balancer target in `docs/deployment-domain-dns.md`. |
| TLS check fails. | Confirm `TLS_MODE`, `TLS_CLUSTER_ISSUER`, `TLS_SECRET_NAME`, Certificate status, and provider-specific ingress TLS requirements in `docs/deployment-tls.md`. |
| Smoke test fails after rollout succeeds. | Roll back first if public traffic is affected, then inspect ingress, backend logs, and telemetry. |
| Pods are `OOMKilled` or unschedulable. | Apply the resource tuning guidance before another promotion attempt. |

## Guardrails

- Do not deploy public traffic from `latest`.
- Do not skip `kubectl rollout status`; `kubectl apply` only confirms the API accepted the manifest.
- Do not treat frontend rollout success as backend success. Verify both deployments.
- Do not enable frontend ingress isolation until the ingress-controller selector is confirmed against live pod labels.
- Do not scale backend replicas during rollback while SQLite remains the runtime database.
- Keep release manifests in `/tmp` or another operator-owned path; do not commit rendered environment-specific manifests.
