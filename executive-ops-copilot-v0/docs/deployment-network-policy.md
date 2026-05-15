# Deployment Network Policy

Desk AI includes a baseline Kubernetes NetworkPolicy set for the `desk-ai` namespace. The baseline protects internal service boundaries without adding provider-specific ingress-controller or egress-gateway assumptions.

## Current Baseline

The checked-in policies live in `infra/k8s/network-policy.yaml` and are included in the default kustomization.

| Policy | Selected pods | Allowed inbound traffic |
| --- | --- | --- |
| `backend-ingress` | `app=backend` | Only `app=frontend` pods on TCP `8000`. |
| `ollama-ingress` | `app=ollama` | `app=backend` and `app=ollama-model-pull` pods on TCP `11434`. |

The frontend is intentionally not ingress-isolated in the base manifest. It is the public entry point behind the cluster ingress controller, and the exact ingress-controller namespace and pod labels vary by provider. Restrict frontend ingress after the target controller is selected.

The baseline also does not set egress default-deny. Ollama model pulls, DNS, provider metadata services, certificate controllers, and future observability exporters all vary by cluster. Add egress restrictions only after those dependencies are known and tested.

## Required CNI Behavior

NetworkPolicy is enforced only when the cluster CNI supports it. Before relying on these policies, confirm the selected hyperscaler cluster uses an enforcing CNI such as Calico, Cilium, Antrea, or a provider-supported equivalent. If the CNI does not enforce NetworkPolicy, these manifests apply successfully but do not isolate traffic.

## Preflight Checks

After applying manifests to a cluster, verify that policies exist:

```bash
kubectl -n desk-ai get networkpolicy
kubectl -n desk-ai describe networkpolicy backend-ingress
kubectl -n desk-ai describe networkpolicy ollama-ingress
```

Confirm the selected pods match the expected labels:

```bash
kubectl -n desk-ai get pods --show-labels
```

The model-pull job pod must carry `app=ollama-model-pull`; backend and frontend pods must keep their `app=backend` and `app=frontend` labels.

## Validation Flow

After a rollout, run the normal public smoke test first:

```bash
./scripts/smoke-deploy.sh https://desk-ai.example.com
```

Then verify that the frontend can still reach the backend through `/api` and the backend can still reach Ollama:

```bash
kubectl -n desk-ai logs deployment/backend --tail=100
kubectl -n desk-ai logs deployment/ollama --tail=100
```

If the backend rollout stalls after network policies are enabled, check whether the frontend-to-backend or backend-to-Ollama path is blocked before changing application code.

## Provider-Specific Hardening

Once the target ingress controller and CNI are known, add an overlay that also isolates the frontend. For a standard nginx ingress controller installed in an `ingress-nginx` namespace, the shape is:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-ingress
  namespace: desk-ai
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 80
```

For managed ingress controllers, replace the namespace and pod selectors with provider-specific labels. Test this overlay before public cutover because a selector mismatch will make the public site unreachable.

## Future Egress Policy

Do not enable egress default-deny until these destinations are explicit:

- Kubernetes DNS service and labels.
- Ollama model registry or approved egress gateway.
- Certificate-manager or provider-managed certificate dependencies.
- External telemetry/logging endpoints, if configured.
- Managed database endpoint, after SQLite is replaced.

When those dependencies are known, add egress policies one dependency at a time and rerun the smoke test plus an actual model-backed request.

## Guardrails

- Keep backend reachable only from frontend pods.
- Keep Ollama reachable only from backend and the model-pull job.
- Do not assume NetworkPolicy enforcement without verifying the CNI.
- Do not add frontend ingress isolation until the ingress-controller labels are confirmed.
- Do not add egress default-deny until DNS, model pulls, certs, telemetry, and database endpoints are mapped.

