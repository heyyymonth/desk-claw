# Deployment Public Access Controls

This document defines the repo-supported public access control path for Desk AI. It does not replace application login/session work in `docs/deployment-auth-session.md`; it prevents accidental broad ingress exposure while the edge and identity decisions are being made.

## Access Modes

| Mode | Release inputs | Use case | What the repo enforces |
| --- | --- | --- | --- |
| `ip-allowlist` | `PUBLIC_ACCESS_MODE=ip-allowlist`, `PUBLIC_ALLOWED_CIDRS=<cidr,cidr>` | Private pilot, internal demo, operator-only validation. | Adds the nginx Ingress `whitelist-source-range` annotation and stores the CIDR decision on the Ingress. |
| `provider-gated` | `PUBLIC_ACCESS_MODE=provider-gated`, `PUBLIC_WAF_POLICY_ID`, `PUBLIC_DDOS_PROTECTION=true`, `PUBLIC_IDENTITY_PROVIDER` | Public edge path where the hyperscaler load balancer, WAF, DDoS controls, and identity provider are already configured outside the app manifest. | Adds auditable Ingress annotations for the selected WAF, DDoS posture, and identity provider. |

The Kubernetes Ingress API exposes HTTP/HTTPS routes through an ingress controller, and controller behavior can vary by implementation. The checked-in path uses `ingressClassName: nginx`; nginx ingress supports `nginx.ingress.kubernetes.io/whitelist-source-range` as a comma-separated CIDR allowlist.

## Private Pilot Render

Use this before real login/session auth is implemented or before the WAF and identity provider are fully wired:

```bash
PUBLIC_HOST=desk-ai.example.com \
  REQUIRE_PUBLIC_ACCESS_CONTROL=true \
  PUBLIC_ACCESS_MODE=ip-allowlist \
  PUBLIC_ALLOWED_CIDRS=203.0.113.10/32,198.51.100.0/24 \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  STORAGE_CLASS_NAME=desk-ai-retain \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

This mode is not a substitute for user login. It is a network exposure limiter for controlled access.

## Provider-Gated Render

Use this only after the provider edge stack exists outside the repo:

```bash
PUBLIC_HOST=desk-ai.example.com \
  REQUIRE_PUBLIC_ACCESS_CONTROL=true \
  PUBLIC_ACCESS_MODE=provider-gated \
  PUBLIC_WAF_POLICY_ID=aws-wafv2-desk-ai-prod \
  PUBLIC_DDOS_PROTECTION=true \
  PUBLIC_IDENTITY_PROVIDER=okta-workforce \
  REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  STORAGE_CLASS_NAME=desk-ai-retain \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
```

`provider-gated` records the provider controls on the Ingress; it does not create AWS WAF, Cloud Armor, Azure WAF, DDoS protection, or the identity provider tenant. Those remain provider-owned resources.

## Verification

After applying the release, verify the access-control decision on the live Ingress:

```bash
PUBLIC_ACCESS_MODE=ip-allowlist \
  PUBLIC_ALLOWED_CIDRS=203.0.113.10/32,198.51.100.0/24 \
  ./scripts/check-public-access.sh desk-ai.example.com
```

For provider-gated mode:

```bash
PUBLIC_ACCESS_MODE=provider-gated \
  PUBLIC_WAF_POLICY_ID=aws-wafv2-desk-ai-prod \
  PUBLIC_DDOS_PROTECTION=true \
  PUBLIC_IDENTITY_PROVIDER=okta-workforce \
  ./scripts/check-public-access.sh desk-ai.example.com
```

The checker validates:

- the Ingress host and TLS host match `PUBLIC_HOST`;
- the Ingress declares the expected `desk.ai/public-access-mode`;
- IP allowlist mode has the expected nginx CIDR allowlist;
- provider-gated mode records the selected WAF policy, DDoS protection, and identity provider;
- backend and Ollama services are not exposed as `LoadBalancer`, `NodePort`, or `externalIPs`;
- `Ingress/frontend` routes only to `Service/frontend`, and no alternate Ingress routes to frontend, backend, or Ollama services.

If a provider-specific rollout intentionally uses a different public service name, set `PUBLIC_SERVICE_NAME`. Keep `CHECK_PRIVATE_SERVICE_EXPOSURE=true` for production checks; disabling it is only for narrowly scoped debugging when the checker does not have list access.

## Provider Responsibilities

Before broad exposure, the platform owner must confirm:

- the selected ingress/load balancer has a WAF policy attached;
- DDoS protection is enabled or explicitly covered by the provider's managed baseline;
- identity provider tenant/application is selected and ready for backend session implementation;
- rate limits and request-size limits are configured at the ingress or WAF layer;
- public access logs are retained in the provider logging system;
- emergency disablement is known, such as removing DNS, removing the ingress rule, or applying an allowlist with no public ranges.

## Production Gate

Do not treat the deployment as broad-public ready until:

- the release is rendered with `REQUIRE_PUBLIC_ACCESS_CONTROL=true`;
- `scripts/check-public-access.sh` passes against the deployed Ingress;
- backend and model runtime services remain private behind the frontend proxy;
- public DNS and TLS checks pass;
- runtime secrets are required and verified;
- real app auth/session work has been implemented or the deployment remains IP-restricted;
- WAF, DDoS, and identity-provider decisions are recorded in the deployment ticket.

## References

- [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [ingress-nginx annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
