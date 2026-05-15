# Deployment GitHub Pages Preview

GitHub Pages is an option for a static Desk AI frontend preview. It is not a full production hosting target for the current application because Pages cannot run FastAPI, ADK, Ollama, SQLite/Postgres, or the nginx same-origin `/api` proxy.

Use GitHub Pages only when the backend is already exposed separately over HTTPS and has production-ready CORS, auth/session handling, public access controls, runtime secrets, and model hosting.

## Supported Shape

```text
Browser -> GitHub Pages static React bundle
Browser -> public HTTPS backend API origin
Backend -> ADK -> Ollama or external model endpoint
Backend -> SQLite or managed Postgres
```

This is a split-origin shape. It is different from the Kubernetes path, where the browser calls the frontend origin and nginx proxies `/api` privately to the backend service.

## Not Supported On Pages

- Running the backend, ADK, Ollama, Postgres, or any container.
- Serving the app through the checked-in frontend nginx `/api` reverse proxy.
- Keeping the backend private behind the frontend service.
- Enforcing Kubernetes NetworkPolicy, StorageClass, VolumeSnapshot, or runtime Secret checks.
- Treating Pages as a replacement for the managed Kubernetes deployment gate.

## Workflow

The repository includes a manual GitHub Actions workflow:

```text
Desk AI Pages Preview
```

Run it from GitHub Actions with:

```text
api_base_url: https://api.desk-ai.example.com
base_path: /desk-claw/
```

Use `base_path: /desk-claw/` for the default project URL:

```text
https://heyyymonth.github.io/desk-claw/
```

Use `base_path: /` only when GitHub Pages is configured with a custom domain for the repository.

The workflow validates that `api_base_url` starts with `https://`, runs frontend tests, builds the Vite app with `VITE_API_BASE_URL=<api_base_url>`, uploads the static `dist` artifact, and deploys it to Pages.

## Backend CORS

Because GitHub Pages is a different browser origin from the backend API, the backend must explicitly allow the Pages origin.

For the default project URL, the CORS origin is the scheme and host only:

```text
https://heyyymonth.github.io
```

Do not include the project path `/desk-claw/` in `CORS_ALLOWED_ORIGINS`; CORS origins do not include paths.

When rendering the backend/API release for a Pages preview, pass:

```bash
CORS_ALLOWED_ORIGINS=https://heyyymonth.github.io \
  PUBLIC_HOST=api.desk-ai.example.com \
  TLS_SECRET_NAME=desk-ai-api-tls \
  TLS_MODE=cert-manager \
  TLS_CLUSTER_ISSUER=letsencrypt-prod \
  ./scripts/render-release-k8s.sh git-<sha> /tmp/desk-ai-api-release.yaml
```

If the Pages site uses a custom domain, set `CORS_ALLOWED_ORIGINS` to that custom origin instead, for example `https://desk-ai.example.com`.

## Production Gate

Do not use the Pages preview as the public production path until these are true:

- A real public backend origin exists and passes `scripts/smoke-deploy.sh`.
- Backend CORS explicitly allows the Pages origin.
- The backend is protected by real login/session auth, not frontend-bundled admin or actor tokens.
- Public access controls, WAF/DDoS posture, DNS, TLS, runtime secrets, observability, model runtime, and database runtime checks have passed for the backend deployment.
- The deployment ticket records that this is a split-origin static frontend, not the default Kubernetes same-origin frontend/proxy shape.

## Recommendation

For the first public Desk AI product deployment, keep the Kubernetes Ingress path as the primary target. Use GitHub Pages for a static preview only after the backend is separately hosted and secured.
