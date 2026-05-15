# Deployment Provider Selection

This guide turns the first outside-repo dependency, "choose hyperscaler and Kubernetes flavor," into an explicit decision record. The repo is now prepared for managed Kubernetes, but the provider choice still depends on account ownership, budget, region, identity stack, and whether Ollama runs in-cluster.

## Required Decision

Choose one managed Kubernetes target before public deployment:

```text
Provider: AWS EKS | Google GKE | Azure AKS | other managed Kubernetes
Cluster mode: managed node pools / standard mode / autopilot-style mode
Primary region:
Public hostname:
Model hosting shape: in-cluster Ollama | GPU node pool | external private model endpoint
```

Do not use a self-managed Kubernetes control plane for the first public Desk AI deployment. The app already has enough operational surface area in ingress, TLS, model warmup, storage, telemetry, and auth; self-managing the control plane would add avoidable risk.

## Desk AI Cluster Requirements

The selected platform must support:

| Capability | Required For |
| --- | --- |
| Managed Kubernetes control plane | Reduces control-plane patching and availability burden. |
| Linux application node pool | Runs frontend, backend, and supporting controllers. |
| Optional GPU or high-memory node pool | Needed if Ollama stays in-cluster and model latency matters. |
| Persistent `ReadWriteOnce` volumes | Required for the current SQLite and Ollama PVCs. |
| Storage snapshots or managed backup | Required before real user data is accepted. |
| Ingress controller or provider HTTP(S) load balancer | Public frontend entry point and TLS termination. |
| NetworkPolicy enforcement | Makes the checked-in backend/Ollama isolation meaningful. |
| Secret-manager integration | Produces `desk-ai-secrets` without committing values. |
| Container registry pull path | Pulls GHCR images, either public packages or image-pull credentials. |
| Metrics backend | Scrapes backend `/metrics` and ingress-controller/load-balancer metrics. |
| Managed Postgres option | Required before backend horizontal scaling. |
| OIDC/SAML identity integration | Required before public admin and telemetry access. |

## Provider Fit

| Option | Best Fit | Desk AI Notes |
| --- | --- | --- |
| AWS EKS | Choose this if the production account, DNS, IAM, WAF, databases, or enterprise controls already live in AWS. | EKS provides a managed, Kubernetes-conformant control plane across Availability Zones and supports managed node groups. For in-cluster Ollama, use EC2-backed managed node groups or another compute option that supports the needed GPU/high-memory profile. Confirm Amazon VPC CNI NetworkPolicy support or deploy a supported policy engine before relying on the checked-in policies. |
| Google GKE | Choose this if there is no existing cloud constraint and the goal is the fastest Kubernetes-native first deployment. | GKE has a clear Autopilot vs Standard split. Autopilot is the lower-ops default for most workloads, but Desk AI may need Standard or Standard plus Autopilot workloads when you want direct control over node pools, GPU capacity, storage, and ingress behavior. GKE docs explicitly cover GPU choices across Autopilot and Standard. |
| Azure AKS | Choose this if Microsoft Entra ID, Azure networking, Azure Database for PostgreSQL, or enterprise governance are already the center of gravity. | AKS has Standard and more managed Automatic-style modes. Use node pools for application and GPU/high-memory separation. Confirm Azure Network Policy or another supported NetworkPolicy implementation is enabled before treating the checked-in policies as enforced. |
| Other managed Kubernetes | Choose only when there is a clear cost, simplicity, or existing-platform reason. | Must still satisfy the capability table above. Avoid platforms that cannot provide NetworkPolicy enforcement, storage snapshots, private service networking, and a credible GPU/high-memory path if Ollama stays in-cluster. |

## Recommended First Path

If there is no pre-existing cloud commitment, start with:

```text
GKE Standard in one US region
```

Reasoning:

- Desk AI already uses portable Kubernetes manifests, so all three major providers remain viable.
- The current app still uses SQLite on one backend replica; the first public deployment is a controlled pilot, not a highly available production topology.
- Standard mode gives direct control over node pools and storage while still using a managed control plane.
- It leaves room to add GPU/high-memory model capacity, managed Postgres, NetworkPolicy enforcement, and ingress metrics without redesigning the app.

Use EKS instead when AWS is already the account of record. Use AKS instead when Microsoft Entra ID and Azure governance are already the identity and compliance base.

## First Cluster Shape

For a pilot with Ollama in-cluster:

| Pool | Purpose | Initial Shape |
| --- | --- | --- |
| system/general | ingress controller, frontend, backend, monitoring agents | 2 small-to-medium Linux nodes across at least two zones where the provider supports it. |
| model | Ollama | 1 high-memory or GPU-capable node, with taints/tolerations added in a provider overlay before production traffic. |

For a pilot with an external private model endpoint:

| Pool | Purpose | Initial Shape |
| --- | --- | --- |
| system/general | ingress controller, frontend, backend, monitoring agents | 2 small-to-medium Linux nodes. |

Keep backend replicas at `1` until the managed Postgres migration is implemented and cut over. The checked-in manifest validation intentionally fails if SQLite is configured with more than one backend replica.

## Decision Record Template

Copy this into the deployment ticket or runbook once the owner decision is made:

```text
Chosen provider:
Chosen cluster mode:
Primary region:
Reason for provider:
Model hosting shape:
Ingress controller or load balancer:
TLS issuer:
DNS zone owner:
NetworkPolicy implementation:
Secret manager:
Metrics backend:
Persistent storage class:
Backup/snapshot mechanism:
Managed Postgres target:
Identity provider:
Public access controls:
Known constraints:
Approval owner:
Decision date:
```

## Immediate Follow-On Work After Choice

1. Create the managed Kubernetes cluster and verify `kubectl` access.
2. Confirm NetworkPolicy enforcement is active before relying on backend/Ollama isolation.
3. Create or configure image-pull access for GHCR using `docs/deployment-image-access.md`, unless the packages are public.
4. Choose the model-hosting path using `docs/deployment-model-hosting.md`; install GPU dependencies or create the private model endpoint before the first release if needed.
5. Install or select the ingress controller/load-balancer path.
6. Configure DNS using `docs/deployment-domain-dns.md`, then configure TLS using `docs/deployment-tls.md`.
7. Connect the secret manager to a Kubernetes Secret named `desk-ai-secrets` using `docs/deployment-secret-management.md`.
8. Install the observability stack and confirm backend `/metrics` plus ingress errors are scraped.
9. Run `K8S_BASE_DIR=<selected-path> MODEL_ENDPOINT_URL=<external-url-if-needed> REQUIRE_RUNTIME_SECRET=true TLS_MODE=<mode> PUBLIC_HOST=<host> TLS_SECRET_NAME=<secret> ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml`.
10. Apply the release, run `./scripts/check-runtime-secret.sh desk-ai-secrets`, run `MODEL_HOSTING_MODE=<mode> ./scripts/check-model-runtime.sh https://<host>`, run `./scripts/check-public-dns.sh <host>`, run `./scripts/check-public-tls.sh <host>`, then run `./scripts/smoke-deploy.sh https://<host>`.

## References

- [Amazon EKS documentation](https://aws.amazon.com/documentation-overview/eks/)
- [Amazon EKS network security](https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html)
- [GKE mode selection](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode)
- [GKE GPU selection](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gpus)
- [GKE NetworkPolicy enforcement](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/network-policy)
- [AKS core concepts](https://learn.microsoft.com/en-us/azure/aks/core-aks-concepts)
- [AKS NetworkPolicy](https://learn.microsoft.com/en-us/azure/virtual-network/kubernetes-network-policies)
- [AKS GPU nodes](https://learn.microsoft.com/en-us/azure/aks/use-nvidia-gpu)
