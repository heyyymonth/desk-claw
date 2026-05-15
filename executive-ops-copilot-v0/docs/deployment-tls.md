# Deployment TLS

This runbook defines how Desk AI gets a public HTTPS certificate after the domain and DNS path in `docs/deployment-domain-dns.md` is complete.

Kubernetes Ingress terminates TLS at the ingress point by referencing a Kubernetes Secret of type `kubernetes.io/tls`. The TLS hosts must match the Ingress rule host. For the checked-in nginx Ingress path, the recommended first production route is cert-manager with ACME HTTP-01, because it keeps certificate creation and renewal inside the cluster while still leaving DNS ownership explicit.

## Supported TLS Modes

Use one mode per deployed environment:

| Mode | Use When | Release Render Setting |
| --- | --- | --- |
| cert-manager | The cluster has cert-manager installed and ACME HTTP-01 can reach the public ingress over HTTP. | `TLS_MODE=cert-manager TLS_CLUSTER_ISSUER=<issuer>` |
| precreated-secret | A certificate is issued outside the cluster and uploaded as a Kubernetes TLS Secret. | `TLS_MODE=precreated-secret TLS_SECRET_NAME=<secret>` |
| provider-managed | The hyperscaler ingress controller manages certificates through provider-specific annotations or certificate resources. | `TLS_MODE=provider-managed` plus a provider overlay |

The base Ingress contains a cert-manager annotation for local/default rendering. Production release rendering patches that annotation for `cert-manager` mode and removes it for `precreated-secret` or `provider-managed` mode.

## Recommended First Path: cert-manager

External prerequisites:

- cert-manager is installed in the cluster and its CRDs are ready;
- DNS for `PUBLIC_HOST` points to the current Ingress load balancer;
- public HTTP port `80` and HTTPS port `443` are allowed to the ingress controller;
- the ingress controller class matches `INGRESS_CLASS_NAME`, which defaults to `nginx`;
- an operator email address is approved for ACME registration and expiration notices.

Create a staging ClusterIssuer first:

```bash
export ACME_EMAIL=ops@example.com
export ACME_ENV=staging

./scripts/render-cert-manager-issuer.sh letsencrypt-staging /tmp/desk-ai-letsencrypt-staging.yaml
kubectl apply -f /tmp/desk-ai-letsencrypt-staging.yaml
```

Render and apply a staging-certificate release:

```bash
export RELEASE_SHA=<7-40-character-git-sha>
export PUBLIC_HOST=desk-ai.example.com
export TLS_SECRET_NAME=desk-ai-tls

TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-staging \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml

kubectl apply -f /tmp/desk-ai-release.yaml
```

Check that cert-manager created the Certificate and Secret:

```bash
kubectl -n desk-ai get certificate,certificaterequest,order,challenge
kubectl -n desk-ai describe certificate "$TLS_SECRET_NAME"
SKIP_PUBLIC_TLS_PROBE=true ./scripts/check-public-tls.sh "$PUBLIC_HOST"
```

The public OpenSSL trust probe is skipped for staging because Let's Encrypt staging certificates are intentionally not browser-trusted. Once staging issuance succeeds, create the production ClusterIssuer:

```bash
export ACME_EMAIL=ops@example.com
export ACME_ENV=prod

./scripts/render-cert-manager-issuer.sh letsencrypt-prod /tmp/desk-ai-letsencrypt-prod.yaml
kubectl apply -f /tmp/desk-ai-letsencrypt-prod.yaml
```

Render and apply the production-certificate release:

```bash
TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml

kubectl apply -f /tmp/desk-ai-release.yaml
kubectl -n desk-ai rollout status deployment/frontend --timeout=300s
./scripts/check-public-dns.sh "$PUBLIC_HOST"
./scripts/check-public-tls.sh "$PUBLIC_HOST"
./scripts/smoke-deploy.sh "https://${PUBLIC_HOST}"
```

## Pre-Created TLS Secret

Use this when certificates are issued by an existing enterprise PKI, a vendor portal, or a manual ACME flow.

Create or update the Secret out of band:

```bash
kubectl -n desk-ai create secret tls desk-ai-tls \
  --cert=/path/to/fullchain.pem \
  --key=/path/to/private-key.pem \
  --dry-run=client -o yaml | kubectl apply -f -
```

Render the release without the cert-manager annotation:

```bash
TLS_MODE=precreated-secret \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml
```

After applying, verify:

```bash
./scripts/check-public-tls.sh "$PUBLIC_HOST"
```

## Provider-Managed Certificates

Use this when the selected ingress controller expects provider-specific certificate resources or annotations, such as a managed cloud HTTP(S) load balancer certificate.

Render the release with cert-manager disabled:

```bash
TLS_MODE=provider-managed \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME=desk-ai-tls \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml
```

Then add a provider-specific overlay for that cluster's certificate annotations or certificate resources. Keep that overlay separate from `infra/k8s` because the required fields differ across EKS, GKE, AKS, and other ingress controllers.

If the provider does not use a Kubernetes TLS Secret, run the public probe without the Secret requirement:

```bash
REQUIRE_TLS_SECRET=false ./scripts/check-public-tls.sh "$PUBLIC_HOST"
```

## Failure Triage

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Certificate stays pending. | DNS, ingress class, HTTP port `80`, or ACME challenge routing is wrong. | Run `scripts/check-public-dns.sh`, inspect `challenge` resources, and check ingress-controller logs. |
| Secret is missing. | cert-manager did not issue, or the pre-created Secret was not applied in `desk-ai`. | Inspect `kubectl -n desk-ai describe certificate "$TLS_SECRET_NAME"` or recreate the Secret. |
| OpenSSL verification fails. | Staging certificate, wrong host, incomplete chain, expired cert, or untrusted issuer. | Use production issuer for public traffic and confirm the certificate SAN includes `PUBLIC_HOST`. |
| Browser redirects loop or serves HTTP. | Ingress controller TLS/redirect behavior differs from nginx annotations. | Review the selected ingress-controller TLS docs and provider-specific annotations. |
| ACME rate limit errors. | Production issuer was tested repeatedly. | Use staging first; wait for rate-limit windows before retrying production. |

## References

- [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)
- [cert-manager annotated Ingress](https://cert-manager.io/docs/usage/ingress/)
- [cert-manager ACME HTTP-01](https://cert-manager.io/docs/configuration/acme/http01/)
