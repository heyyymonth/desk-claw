# Deployment Network Policy

Desk AI includes a baseline Kubernetes NetworkPolicy set for the `desk-ai` namespace. The baseline protects internal service boundaries without adding provider-specific egress-gateway assumptions. Production releases can also render a frontend ingress policy after the target ingress-controller labels are confirmed.

## Current Baseline

The checked-in policies live in `infra/k8s/network-policy.yaml` and are included in the default kustomization.

| Policy | Selected pods | Allowed inbound traffic |
| --- | --- | --- |
| `backend-ingress` | `app=backend` | Only `app=frontend` pods on TCP `8000`. |
| `ollama-ingress` | `app=ollama` | `app=backend` and `app=ollama-model-pull` pods on TCP `11434`. |

The frontend is intentionally not ingress-isolated in the base manifest. It is the public entry point behind the cluster ingress controller, and the exact ingress-controller namespace and pod labels vary by provider. Restrict frontend ingress during release rendering after the target controller is selected.

The baseline also does not set egress default-deny. Ollama model pulls, DNS, provider metadata services, certificate controllers, and future observability exporters all vary by cluster. Add egress restrictions only after those dependencies are known and tested.

## Required CNI Behavior

NetworkPolicy is enforced only when the cluster CNI supports it. Before relying on these policies, confirm the selected hyperscaler cluster uses an enforcing CNI such as Calico, Cilium, Antrea, or a provider-supported equivalent. If the CNI does not enforce NetworkPolicy, these manifests apply successfully but do not isolate traffic.

Kubernetes documents this as a network-plugin requirement: a `NetworkPolicy` resource without a controller that implements it has no isolation effect. Treat the CNI check as a deployment gate, not a cosmetic manifest check.

## Release Render Inputs

Use these inputs when rendering a production release after CNI enforcement is confirmed:

```bash
REQUIRE_NETWORK_POLICY_ENFORCEMENT=true \
  NETWORK_POLICY_PROVIDER=cilium \
  NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true \
  FRONTEND_INGRESS_POLICY=enabled \
  INGRESS_CONTROLLER_NAMESPACE=ingress-nginx \
  INGRESS_CONTROLLER_POD_SELECTOR=app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

The renderer records `desk.ai/network-policy-provider` and `desk.ai/network-policy-enforcement` annotations on the baseline policies. When `FRONTEND_INGRESS_POLICY=enabled`, it also renders `NetworkPolicy/frontend-ingress` so only the selected ingress-controller pods can connect to frontend port `80`.

Do not set `FRONTEND_INGRESS_POLICY=enabled` until `INGRESS_CONTROLLER_NAMESPACE` and `INGRESS_CONTROLLER_POD_SELECTOR` have been checked against the actual controller pods:

```bash
kubectl get pods -A --show-labels | grep -E 'ingress|gateway|load-balancer'
```

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

Run the repo-supported checker after deployment:

```bash
NETWORK_POLICY_PROVIDER=cilium \
  REQUIRE_FRONTEND_INGRESS_POLICY=true \
  INGRESS_CONTROLLER_NAMESPACE=ingress-nginx \
  INGRESS_CONTROLLER_POD_SELECTOR=app.kubernetes.io/name=ingress-nginx,app.kubernetes.io/component=controller \
  ./scripts/check-network-policy.sh desk-ai
```

If the selected provider does not expose obvious Calico, Cilium, Antrea, Amazon VPC CNI, or Azure NPM pod evidence, set `NETWORK_POLICY_ENFORCEMENT_CONFIRMED=true` only after confirming the provider-side NetworkPolicy feature is enabled for the cluster.

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

Once the target ingress controller and CNI are known, render frontend isolation instead of hand-editing YAML. For a standard nginx ingress controller installed in an `ingress-nginx` namespace, the rendered shape is:

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
              app.kubernetes.io/component: controller
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
