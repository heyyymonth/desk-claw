# Kubernetes Deployment

This directory adds a lean Kubernetes layer for the three-service Desk Claw / Executive Ops Copilot app.

```text
User
  -> Ingress
  -> frontend Service
  -> frontend Pod
  -> web-backend Service
  -> web-backend Pod
  -> ai-backend Service
  -> ai-backend Pod
  -> external model providers
```

Docker Compose remains the local development and smoke-test path. Kubernetes is for production-style container orchestration after images have been published to GHCR.

## Services

| Service | Image placeholder | Container port | Kubernetes Service |
| --- | --- | --- | --- |
| Frontend | `ghcr.io/heyyymonth/desk-claw-frontend:REPLACE_TAG` | `80` | `frontend:80` |
| Web Backend | `ghcr.io/heyyymonth/desk-claw-web-backend:REPLACE_TAG` | `8000` | `web-backend:8000` |
| AI Backend | `ghcr.io/heyyymonth/desk-claw-ai-backend:REPLACE_TAG` | `9000` | `ai-backend:9000` |

The Web Backend uses `AI_BACKEND_URL=http://ai-backend:9000`. The frontend nginx config proxies `/api/` to `web-backend:8000`; the `WEB_BACKEND_URL` env var is present for consistency but browser code does not receive provider secrets or the AI Backend URL.

## Configure Images

Replace `REPLACE_TAG` with a published release tag or SHA tag before applying:

```bash
rg 'REPLACE_TAG' infra/k8s
```

For quick local testing with `kind` or `minikube`, either use a published GHCR tag or load locally built images into the cluster and update the image fields accordingly.

## Provider Secrets

Only `ai-backend` reads provider keys and provider base URLs. The checked-in file is an example only and is intentionally not included in `kustomization.yaml`, so `kubectl apply -k infra/k8s` will not overwrite real secrets with blanks.

Create a local secret file that is not committed:

```bash
cp infra/k8s/ai-provider-secret.example.yaml infra/k8s/secrets.yaml
```

Edit `infra/k8s/secrets.yaml` and replace the blank key values with real values. Apply the secret before or after the workloads:

```bash
kubectl apply -f infra/k8s/secrets.yaml
```

Or create the secret from shell values:

```bash
kubectl create namespace desk-claw --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic ai-provider-secret \
  -n desk-claw \
  --from-literal=OLLAMA_API_KEY="$OLLAMA_API_KEY" \
  --from-literal=OLLAMA_BASE_URL="https://ollama.com/api" \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
  --from-literal=OPENAI_BASE_URL="https://api.openai.com/v1" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --from-literal=ANTHROPIC_BASE_URL="https://api.anthropic.com" \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --from-literal=GEMINI_BASE_URL="https://generativelanguage.googleapis.com" \
  --dry-run=client -o yaml | kubectl apply -f -
```

If the secret is missing, the AI Backend still starts because all provider secret references are optional. Provider health reports missing auth until keys are configured.

## Deploy

```bash
kubectl apply -k infra/k8s
kubectl get pods -n desk-claw
kubectl get svc -n desk-claw
```

Check logs:

```bash
kubectl logs -n desk-claw deployment/frontend
kubectl logs -n desk-claw deployment/web-backend
kubectl logs -n desk-claw deployment/ai-backend
```

Port-forward for local verification:

```bash
kubectl port-forward -n desk-claw svc/frontend 3000:80
kubectl port-forward -n desk-claw svc/web-backend 8000:8000
kubectl port-forward -n desk-claw svc/ai-backend 9000:9000
```

Then test:

```bash
curl http://localhost:3000/
curl http://localhost:8000/health
curl http://localhost:9000/health
curl http://localhost:9000/health/providers
```

With an ingress controller installed, add `desk-claw.local` to `/etc/hosts` for your cluster ingress address and open:

```text
http://desk-claw.local
```

## Local Cluster Notes

For `minikube`, enable ingress if you want to test `ingress.yaml`:

```bash
minikube addons enable ingress
minikube tunnel
```

For `kind`, install an ingress controller before testing the Ingress. Without an ingress controller, use the port-forward commands above.

## Expected Missing-Key Behavior

Missing model provider keys should not crash the pods. Expected behavior without secrets:

- `ai-backend` `/health` returns `ok`.
- `ai-backend` `/health/providers` returns degraded provider metadata with `auth: missing`.
- model chat endpoints return controlled provider configuration errors.
- frontend and web-backend remain reachable.
