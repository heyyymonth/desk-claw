# Deployment Rollout Runbook

This runbook defines how to promote, verify, and roll back a Desk AI Kubernetes release. It assumes the public deployment path uses immutable `git-<sha>` image tags from GHCR, not mutable `latest` tags.

## Prerequisites

Before promoting a commit:

- GitHub Actions is green for the commit being deployed.
- GHCR contains both application images:
  - `ghcr.io/heyyymonth/desk-ai-backend:git-<sha>`
  - `ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>`
- `kubectl config current-context` points at the intended cluster.
- The `desk-ai-secrets` Secret exists in the `desk-ai` namespace or is created by the configured secret-management controller.
- Ingress host, TLS, DNS, and any cloud firewall/security-group rules are already configured.
- Ollama capacity and timeout values have been reviewed against `docs/deployment-resource-tuning.md`.

Set these shell variables for the commands below:

```bash
export RELEASE_SHA=<7-40-character-git-sha>
export RELEASE_TAG="git-${RELEASE_SHA}"
export RELEASE_FILE="/tmp/desk-ai-${RELEASE_TAG}.yaml"
export PUBLIC_URL="https://desk-ai.example.com"
```

Confirm the target context before applying anything:

```bash
kubectl config current-context
kubectl get namespace desk-ai || true
kubectl -n desk-ai get deployments || true
```

## First Cluster Bootstrap

Run this once per fresh cluster or namespace. The model pull can take a long time on cold storage or CPU-only nodes.

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/ollama.yaml
kubectl -n desk-ai rollout status deployment/ollama --timeout=300s

kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
```

If the model changes and the job already exists, delete and recreate the job after updating the config:

```bash
kubectl -n desk-ai delete job ollama-pull-gemma4 --ignore-not-found
kubectl apply -f infra/k8s/ollama-model-job.yaml
kubectl -n desk-ai wait --for=condition=complete job/ollama-pull-gemma4 --timeout=1800s
```

## Promote a Commit Tag

Render the release manifest with the immutable commit tag:

```bash
./scripts/render-release-k8s.sh "$RELEASE_TAG" "$RELEASE_FILE"
```

Review the application image tags before applying:

```bash
grep -E "image: ghcr.io/heyyymonth/desk-ai-(backend|frontend):" "$RELEASE_FILE"
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

Run the public smoke check:

```bash
./scripts/smoke-deploy.sh "$PUBLIC_URL"
```

A release is complete only after both rollout status commands and the smoke test pass.

## Preferred Rollback: Promote the Last Known Good Commit

The safest rollback is another immutable release render using the last known good commit tag. This leaves a clear manifest and image-tag record.

```bash
export PREVIOUS_RELEASE_SHA=<last-known-good-git-sha>
export PREVIOUS_RELEASE_TAG="git-${PREVIOUS_RELEASE_SHA}"
export ROLLBACK_FILE="/tmp/desk-ai-${PREVIOUS_RELEASE_TAG}.yaml"

./scripts/render-release-k8s.sh "$PREVIOUS_RELEASE_TAG" "$ROLLBACK_FILE"
kubectl apply -f "$ROLLBACK_FILE"
kubectl -n desk-ai rollout status deployment/backend --timeout=600s
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
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
| Smoke test fails after rollout succeeds. | Roll back first if public traffic is affected, then inspect ingress, backend logs, and telemetry. |
| Pods are `OOMKilled` or unschedulable. | Apply the resource tuning guidance before another promotion attempt. |

## Guardrails

- Do not deploy public traffic from `latest`.
- Do not skip `kubectl rollout status`; `kubectl apply` only confirms the API accepted the manifest.
- Do not treat frontend rollout success as backend success. Verify both deployments.
- Do not scale backend replicas during rollback while SQLite remains the runtime database.
- Keep release manifests in `/tmp` or another operator-owned path; do not commit rendered environment-specific manifests.
