# Deployment Domain and DNS

This runbook turns the public hostname decision into a repeatable release step. Desk AI exposes only the frontend Ingress publicly; the backend stays private behind the frontend nginx `/api` proxy.

Kubernetes Ingress requires an ingress controller before the resource has any effect, and host rules route HTTP(S) requests only when the request host and path match the Ingress spec. ExternalDNS can automate this later from Ingress hosts or annotations, but the first production path keeps DNS ownership explicit.

## Required Decisions

Record these before public cutover:

```text
Public hostname:
DNS zone owner:
DNS provider/account:
Ingress controller/load balancer:
TLS Secret name:
TLS issuer path:
Firewall/security-group owner:
```

Use a subdomain for the first deployment, for example:

```text
desk-ai.example.com
```

Prefer a `CNAME` from that subdomain to the ingress controller load balancer hostname. If the ingress controller publishes a static IP instead of a hostname, use `A` and `AAAA` records. Avoid an apex/root domain for the first cut unless the DNS provider supports Alias or ANAME records for the chosen load balancer.

## Render the Public Host

The checked-in Ingress keeps `desk-ai.example.com` as a placeholder. Do not hand-edit `infra/k8s/ingress.yaml` for production. Patch the host and TLS Secret at release-render time:

```bash
export RELEASE_SHA=<7-40-character-git-sha>
export PUBLIC_HOST=desk-ai.example.com
export TLS_SECRET_NAME=desk-ai-tls

./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml
```

For private GHCR packages, render the private image-pull overlay with the same host settings:

```bash
K8S_BASE_DIR=infra/k8s-overlays/private-ghcr \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml
```

Confirm the rendered manifest no longer contains the placeholder:

```bash
grep -E "host:|secretName:" /tmp/desk-ai-release.yaml
```

## Find the Ingress Target

After applying the release, wait until the ingress controller publishes a target:

```bash
kubectl -n desk-ai get ingress frontend
kubectl -n desk-ai get ingress frontend -o jsonpath='{.status.loadBalancer.ingress[*].hostname}{" "}{.status.loadBalancer.ingress[*].ip}{"\n"}'
```

If both values are blank, the ingress controller or cloud load balancer is not ready yet. Check the ingress controller deployment, service, events, and provider load balancer console before creating DNS records.

## Create the DNS Record

Create one public record in the DNS provider account:

| Ingress Target | Recommended Record |
| --- | --- |
| Load balancer hostname | `CNAME PUBLIC_HOST -> load-balancer-hostname` |
| Static IPv4 address | `A PUBLIC_HOST -> IPv4` |
| Static IPv6 address | `AAAA PUBLIC_HOST -> IPv6` |
| Apex/root domain | Provider-specific Alias/ANAME only; avoid for first cut. |

If you later install ExternalDNS, it can derive records from Ingress hosts or `external-dns.alpha.kubernetes.io/hostname`, but that should be a separate controlled change because it gives a cluster controller write access to the DNS zone.

## Verify DNS and Smoke

Run the DNS check from this repo after the record exists:

```bash
./scripts/check-public-dns.sh "$PUBLIC_HOST"
```

Then smoke test the public path through the same host users will hit:

```bash
./scripts/smoke-deploy.sh "https://${PUBLIC_HOST}"
```

The DNS check compares the current `desk-ai/frontend` Ingress load balancer target with the public hostname's `A`, `AAAA`, and `CNAME` answers. It catches the common case where the manifest host is correct but DNS still points somewhere else.

## Common Failures

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Ingress has no hostname or IP. | Ingress controller or cloud load balancer is not ready. | Inspect ingress-controller pods, service, events, and cloud load balancer provisioning. |
| DNS check points to the wrong target. | DNS record was created against an old load balancer or the wrong zone. | Update the record to the current Ingress target and wait for propagation. |
| CNAME cannot be created. | The requested hostname is an apex/root domain. | Use a subdomain or provider Alias/ANAME support. |
| Smoke test fails after DNS passes. | TLS, firewall, ingress rule, or frontend/backend route issue. | Check TLS Secret readiness, provider firewall/security groups, ingress controller logs, and backend service endpoints. |
| DNS intermittently resolves old values. | Resolver cache or high TTL. | Lower TTL before cutover when possible and wait for previous records to expire. |

## References

- [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [ExternalDNS annotations](https://kubernetes-sigs.github.io/external-dns/latest/docs/annotations/annotations/)
- [ExternalDNS FAQ](https://kubernetes-sigs.github.io/external-dns/latest/docs/faq/)
