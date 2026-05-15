# Deployment Auth And Session Design

This document defines the production authentication and session target for Desk AI. It is required before exposing admin dashboards, AI telemetry, audit logs, billing, or account management to real users.

## Current V0 State

V0 has two local-development trust mechanisms:

| Mechanism | Current use | Production status |
| --- | --- | --- |
| `ADMIN_API_KEY` plus `X-DeskAI-Admin-Key` | Allows `GET /api/audit/ai` and `GET /api/telemetry/ai/dashboard` when configured. | Local/private only. Do not expose as the public admin auth model. |
| `ACTOR_AUTH_TOKEN` plus `X-DeskAI-Actor-Token` and `X-Actor-*` headers | Lets local clients attach trusted actor identity to AI audit rows. | Local/private only. Production actor identity must come from the authenticated session, not browser-supplied identity headers. |
| `VITE_ADMIN_API_KEY` and `VITE_ACTOR_AUTH_TOKEN` | Lets the Vite frontend send the local V0 headers. | Never ship in public frontend builds. CI validates that the public frontend image build does not pass these values. |

The admin key path stays useful for local inspection and private troubleshooting, but it is not user authentication, not RBAC, and not safe for browser-bundled public deployments.

## Target Architecture

Use a backend-for-frontend session model:

1. The React app uses same-origin `/api` only.
2. FastAPI owns login, callback, session validation, role checks, signout, and actor attribution.
3. The browser stores only an opaque session cookie.
4. OAuth/OIDC tokens stay server-side and are never placed in local storage, session storage, or Vite-bundled JavaScript.
5. Backend repositories and AI audit logging derive `actor_id`, email, display name, and roles from the server-side session.

The preferred identity protocol is OpenID Connect using OAuth 2.0 Authorization Code flow with PKCE against the chosen identity provider. This aligns with the OAuth 2.0 Security Best Current Practice and keeps token handling out of the browser bundle.

## Session Cookie Policy

The production session cookie should be host-scoped and server-only:

```text
Set-Cookie: __Host-desk-ai-session=<opaque-id>; Path=/; Secure; HttpOnly; SameSite=Lax
```

Required properties:

- `Secure`: HTTPS only.
- `HttpOnly`: inaccessible to JavaScript.
- `SameSite=Lax` by default; use `Strict` only after testing identity-provider redirect flows.
- `Path=/`.
- no `Domain` attribute when using the `__Host-` prefix.
- short idle timeout, initially 30 minutes.
- absolute session timeout, initially 8-12 hours for admin users.
- session rotation after login and role changes.
- server-side invalidation on signout.

Unsafe methods such as `POST`, `PUT`, `PATCH`, and `DELETE` need CSRF protection when cookie authentication is enabled. Use an origin check plus a CSRF token or double-submit token for browser-initiated mutations.

## Roles And Access

Start with these roles:

| Role | Intended user | Allowed access |
| --- | --- | --- |
| `executive_assistant` | EA persona that schedules meetings. | Home workflow, meeting intake, calendar coordination, recommendation/draft generation, final decision logging, own account page. |
| `workspace_admin` | Admin persona that manages the workspace. | Everything an executive assistant can access, plus Admin Center, rules/settings, account/subscription/billing, audit logs, and AI Technical Dashboard. |
| `technical_admin` | Future operations/security persona. | AI telemetry, audit inspection, deployment health, model/tool failure diagnostics. No billing requirement unless also `workspace_admin`. |

Production authorization should be enforced in FastAPI. Frontend route hiding is only UX and must not be the access-control boundary.

Endpoint policy:

| API area | Production auth requirement |
| --- | --- |
| `GET /api/health` | Public or infrastructure-only. Must not expose secrets or raw user data. |
| Scheduling workflow APIs | Authenticated `executive_assistant`, `workspace_admin`, or equivalent scheduling role. |
| Decision logs | Authenticated user; tenant/user scoping before multi-tenant use. |
| Rules/settings writes | `workspace_admin`. |
| `GET /api/audit/ai` | `workspace_admin` or `technical_admin`. |
| `GET /api/telemetry/ai/dashboard` | `workspace_admin` or `technical_admin`. |
| Account/subscription/billing | `workspace_admin`. |

## Required Backend Changes

1. Add session settings.

   Required future settings:

   - `AUTH_MODE=oidc`
   - `OIDC_ISSUER_URL`
   - `OIDC_CLIENT_ID`
   - `OIDC_CLIENT_SECRET`
   - `OIDC_REDIRECT_URI`
   - `SESSION_SECRET`
   - `SESSION_COOKIE_NAME=__Host-desk-ai-session`
   - `SESSION_IDLE_TIMEOUT_SECONDS`
   - `SESSION_ABSOLUTE_TIMEOUT_SECONDS`
   - `CSRF_SECRET`

2. Add auth endpoints.

   Required API surface:

   - `GET /api/auth/login`
   - `GET /api/auth/callback`
   - `GET /api/auth/me`
   - `POST /api/auth/signout`
   - `POST /api/auth/csrf` or equivalent CSRF token bootstrap

3. Add a server-side session store.

   Acceptable first choices are Redis or Postgres-backed sessions. Do not store production sessions only in process memory because multiple backend replicas will need shared session validation after the Postgres migration.

4. Replace header-derived identity.

   `get_actor_context()` should read the authenticated session and return the session subject. The current `X-Actor-*` headers should become local-only compatibility or be removed from production builds.

5. Replace admin key access.

   `require_admin_access()` should become a role check against session roles. `ADMIN_API_KEY` can remain as a local/private emergency mechanism only when the public ingress is not exposed.

6. Add audit events for auth.

   Log sign-in success, sign-in failure, signout, session expiry, role denial, and admin telemetry access. Do not log tokens, authorization codes, or raw cookies.

7. Add tests.

   Required tests:

   - unauthenticated workflow request returns `401` when production auth is enabled;
   - `executive_assistant` cannot access billing, audit, or telemetry admin endpoints;
   - `workspace_admin` can access admin endpoints;
   - actor identity in `ai_audit_log` comes from session claims, not spoofed headers;
   - signout invalidates the server-side session;
   - CSRF protection blocks unsafe methods without a valid token.

## Required Frontend Changes

1. Remove production use of `VITE_ADMIN_API_KEY` and `VITE_ACTOR_AUTH_TOKEN`.
2. Replace `adminHeaders()` and `actorHeaders()` with credentialed same-origin requests:

   ```ts
   fetch('/api/telemetry/ai/dashboard', { credentials: 'include' })
   ```

3. Add `/api/auth/me` bootstrap at app load to get user, roles, account, and feature visibility.
4. Gate Admin Center, AI Dashboard, billing, and settings in the UI based on server-returned roles.
5. Keep route checks defensive: hidden UI is not permission.
6. Make signout call `POST /api/auth/signout` and clear client state after the server invalidates the session.

## Kubernetes And Secret Changes

Do not add OIDC/session secrets to the live Kubernetes Secret until the backend reads them. When implementation starts, extend the provider secret manager or External Secrets contract with:

```text
OIDC_ISSUER_URL
OIDC_CLIENT_ID
OIDC_CLIENT_SECRET
SESSION_SECRET
CSRF_SECRET
```

The public frontend image must be built without:

```text
VITE_ADMIN_API_KEY
VITE_ACTOR_AUTH_TOKEN
```

CI validates this for the frontend container build.

## Rollout Plan

1. Select identity provider and required claims.

   Required claims: stable subject, email, display name, groups or roles, and tenant/workspace identifier before multi-tenant use.

2. Implement auth in private mode.

   Keep public ingress restricted while adding session middleware, auth endpoints, role checks, and tests.

3. Run dual path in staging.

   Keep local `ADMIN_API_KEY` disabled in the browser build. Validate that all admin screens work through session auth only.

4. Cut over admin endpoints.

   Replace `require_admin_access()` on audit and telemetry endpoints with role-based session access.

5. Cut over actor attribution.

   Store session subject in AI audit events and ignore browser-supplied actor headers in production.

6. Remove public exposure blockers.

   Expose admin dashboards only after role checks, CSRF protection, cookie security, signout, and audit events are verified.

## Deployment Gate

Do not expose admin dashboards publicly until all are true:

- OIDC login and callback work through the public host over HTTPS.
- Session cookie uses `Secure`, `HttpOnly`, host-scoped path, and a tested `SameSite` mode.
- Unsafe methods have CSRF protection.
- Admin/audit/telemetry endpoints use server-side role checks.
- Frontend production build contains no `VITE_ADMIN_API_KEY` or `VITE_ACTOR_AUTH_TOKEN`.
- Actor identity in audit rows comes from the session.
- Signout invalidates the server-side session.
- Authentication and authorization events are auditable without storing secrets.
- Admin access has been tested with at least one allowed and one denied persona.

## References

- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://www.ietf.org/rfc/rfc9700.html)

