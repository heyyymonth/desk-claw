# Deployment Secret Management

This runbook defines how production runtime secrets reach the backend without committing values to the repo. The backend reads `desk-ai-secrets` through Kubernetes `envFrom`; public releases should require that Secret instead of treating it as optional.

Kubernetes Secrets keep sensitive values out of application images and Pod specs, but they still require cluster controls: encryption at rest for etcd, least-privilege RBAC, and narrow workload access. The recommended first production path is External Secrets Operator backed by the chosen hyperscaler secret manager, because it synchronizes provider-managed values into a normal Kubernetes Secret that the existing backend deployment can consume.

## Runtime Secret Contract

The Kubernetes Secret must live in the `desk-ai` namespace:

```text
Secret name: desk-ai-secrets
Type: Opaque
Required keys:
  ADMIN_API_KEY
  ACTOR_AUTH_TOKEN
```

Current V0 meaning:

| Key | Purpose | Production Note |
| --- | --- | --- |
| `ADMIN_API_KEY` | Allows private/admin reads for AI audit and telemetry endpoints. | Do not put this in frontend builds. It is not the final public admin auth model. |
| `ACTOR_AUTH_TOKEN` | Lets trusted server-side callers attach actor identity headers. | Browser-supplied actor identity remains untrusted without this token. |

Future OIDC/session secrets are documented in `docs/deployment-auth-session.md`; do not add them to the live Secret until the backend reads them.

## Recommended Path: External Secrets Operator

External prerequisites:

- External Secrets Operator is installed in the cluster;
- the provider secret manager contains one remote secret with `ADMIN_API_KEY` and `ACTOR_AUTH_TOKEN` properties;
- the cluster operator has created a least-privilege `SecretStore` or `ClusterSecretStore`;
- the provider access policy allows only the required remote secret key;
- Kubernetes Secret encryption at rest and RBAC are enabled for the cluster.

The provider-specific `SecretStore` or `ClusterSecretStore` is intentionally not generated here. It depends on AWS Secrets Manager, Google Secret Manager, Azure Key Vault, Vault, or another provider identity path.

Render the application ExternalSecret after the store exists:

```bash
export SECRET_STORE_NAME=desk-ai-runtime-secrets
export SECRET_STORE_KIND=ClusterSecretStore
export REMOTE_SECRET_KEY=desk-ai/production/runtime

./scripts/render-external-secret.sh /tmp/desk-ai-external-secret.yaml
kubectl apply -f /tmp/desk-ai-external-secret.yaml
```

Confirm the controller created the Kubernetes Secret:

```bash
kubectl -n desk-ai get externalsecret desk-ai-secrets
kubectl -n desk-ai get secret desk-ai-secrets
```

Render the release so the backend requires the Secret:

```bash
REQUIRE_RUNTIME_SECRET=true \
  RUNTIME_SECRET_NAME=desk-ai-secrets \
  PUBLIC_HOST="$PUBLIC_HOST" \
  TLS_SECRET_NAME="$TLS_SECRET_NAME" \
  TLS_MODE="$TLS_MODE" \
  TLS_CLUSTER_ISSUER="$TLS_CLUSTER_ISSUER" \
  ./scripts/render-release-k8s.sh "git-${RELEASE_SHA}" /tmp/desk-ai-release.yaml
```

After applying the release, verify the Secret and deployment wiring:

```bash
./scripts/check-runtime-secret.sh desk-ai-secrets
```

## Manual Fallback

Use this only for a controlled pilot or while wiring the provider secret manager. Generate values outside the repo and apply the Secret directly:

```bash
kubectl -n desk-ai create secret generic desk-ai-secrets \
  --from-literal=ADMIN_API_KEY="$(openssl rand -hex 32)" \
  --from-literal=ACTOR_AUTH_TOKEN="$(openssl rand -hex 32)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Then render the production release with `REQUIRE_RUNTIME_SECRET=true` and run:

```bash
./scripts/check-runtime-secret.sh desk-ai-secrets
```

Do not commit the generated Secret manifest. The ignored `infra/k8s/secrets.yaml` file remains local-only.

## Rotation

For External Secrets Operator:

1. Rotate the values in the provider secret manager.
2. Wait for `ExternalSecret.spec.refreshInterval` or force a reconcile using the operator's supported workflow.
3. Confirm the Kubernetes Secret was updated:

   ```bash
   kubectl -n desk-ai get externalsecret desk-ai-secrets
   ./scripts/check-runtime-secret.sh desk-ai-secrets
   ```

4. Restart backend pods because environment variables sourced from Secrets are read when the container starts:

   ```bash
   kubectl -n desk-ai rollout restart deployment/backend
   kubectl -n desk-ai rollout status deployment/backend --timeout=600s
   ```

For manual Secrets, apply the replacement Secret and run the same backend rollout restart.

## Failure Triage

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Backend pods fail with missing Secret. | Release was rendered with `REQUIRE_RUNTIME_SECRET=true` before the Secret existed. | Apply the ExternalSecret or manual Secret in `desk-ai`, then restart rollout. |
| `ExternalSecret` is not ready. | Store reference, provider identity, remote key, or provider permissions are wrong. | Inspect `kubectl -n desk-ai describe externalsecret desk-ai-secrets` and the External Secrets controller logs. |
| Secret exists but check fails for placeholder values. | `secrets.example.yaml` values were copied into production. | Rotate to generated values from the provider secret manager. |
| Admin telemetry returns unauthorized. | `ADMIN_API_KEY` missing, changed without client update, or backend pods not restarted after rotation. | Check the Secret, update the private admin client, and restart backend pods. |
| Actor headers are ignored. | `ACTOR_AUTH_TOKEN` missing or does not match caller header. | Check the Secret and trusted caller configuration. |

## References

- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator overview](https://external-secrets.io/latest/introduction/overview/)
