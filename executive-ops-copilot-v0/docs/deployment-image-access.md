# Deployment Image Access

Desk AI publishes application images to GitHub Container Registry (GHCR):

```text
ghcr.io/heyyymonth/desk-ai-backend:git-<sha>
ghcr.io/heyyymonth/desk-ai-frontend:git-<sha>
```

The deployment decision is whether the cluster pulls those images as public packages or with private GHCR credentials.

## Recommended Decision

For a public product deployment, prefer private GHCR packages plus a Kubernetes image pull Secret:

```text
Package visibility: private
Kubernetes Secret: desk-ai/ghcr-pull-secret
Required token scope: read:packages
Deployment overlay: infra/k8s-overlays/private-ghcr
```

Public packages are simpler for early demos, but they also make the built application images globally pullable. Private packages keep release artifacts behind GitHub package permissions while still allowing the cluster to pull immutable `git-<sha>` tags.

## Option A: Public GHCR Packages

Use this when the deployment is a low-risk demo and there is no concern with public image downloads.

1. In GitHub, open each package:
   - `desk-ai-backend`
   - `desk-ai-frontend`
2. Set package visibility to public.
3. Deploy with the normal release renderer:

```bash
./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
```

No `imagePullSecrets` are required in this path.

## Option B: Private GHCR Packages

Use this for production or customer-facing environments.

Create a GitHub token that can pull the packages. For GHCR private package pulls from outside GitHub Actions, GitHub documents a personal access token classic with at least `read:packages`.

Create or update the Kubernetes pull Secret:

```bash
export GHCR_USERNAME=<github-username>
export GHCR_TOKEN=<classic-pat-with-read-packages>
./scripts/create-ghcr-pull-secret.sh
```

The script creates or updates:

```text
namespace: desk-ai
secret: ghcr-pull-secret
registry: ghcr.io
```

Render the private-GHCR release overlay:

```bash
K8S_BASE_DIR=infra/k8s-overlays/private-ghcr ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-release.yaml
kubectl apply -f /tmp/desk-ai-release.yaml
```

The private overlay patches only the application deployments:

```yaml
imagePullSecrets:
  - name: ghcr-pull-secret
```

Ollama still pulls `ollama/ollama:latest` from the public Ollama image source and does not use the GHCR pull Secret.

## Verification

Confirm the rendered release uses immutable app image tags and the pull Secret reference:

```bash
grep -E "image: ghcr.io/heyyymonth/desk-ai-(backend|frontend):git-" /tmp/desk-ai-release.yaml
grep -A2 "imagePullSecrets:" /tmp/desk-ai-release.yaml
```

After applying, verify the cluster can pull the images:

```bash
kubectl -n desk-ai get pods
kubectl -n desk-ai describe pod -l app=backend | grep -E "Pulled|Failed|ImagePull|ErrImagePull" || true
kubectl -n desk-ai describe pod -l app=frontend | grep -E "Pulled|Failed|ImagePull|ErrImagePull" || true
```

Expected result:

```text
backend and frontend pods reach Running or Ready
no ImagePullBackOff or ErrImagePull events
```

If image pulls fail:

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ErrImagePull` with authentication error | Missing or invalid `ghcr-pull-secret`. | Recreate the Secret with a valid token and reroll the deployment. |
| `ImagePullBackOff` for only backend or frontend | One package lacks permission for the token. | Grant the token owner read access to both GHCR packages. |
| Pull succeeds with public overlay but fails with private overlay | Secret name or namespace mismatch. | Confirm `kubectl -n desk-ai get secret ghcr-pull-secret`. |
| Pull succeeds for old tag but not current tag | CI did not publish the selected commit tag. | Confirm GHCR contains `git-<sha>` for both images before rollout. |

## CI Guard

`./scripts/validate-k8s.sh` now renders and validates both:

- the default public-image manifests;
- the private GHCR overlay with `imagePullSecrets`;
- immutable release manifests for both paths.

This keeps the private package path from drifting while still preserving the simple public-package base manifests.

## References

- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Kubernetes private registry image pulls](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
- [Kubernetes imagePullSecrets](https://kubernetes.io/docs/concepts/containers/images/#using-a-private-registry)
