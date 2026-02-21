# Add Owner Authentication (Phase 1)

> **STATUS: READY FOR IMPLEMENTATION**
>
> Phase 1 of the authentication strategy. See `design.md` for the full
> two-phase roadmap including future multi-user support.

## Overview

Add a password-based login flow so the app can be securely accessed from a browser or mobile device when deployed to the cloud. This is a **single-user, owner-only** authentication layer — no user table, no registration, no email. Just a password, a login page, and a session cookie.

## Motivation

The app currently uses an `X-Admin-Key` header to protect admin endpoints, with all content endpoints open. This works for local development and CLI access but breaks down for cloud deployments:

- **Browsers can't send custom headers** without JavaScript — there's no login page, so visiting a deployed instance exposes all content endpoints with zero authentication.
- **Mobile/PWA access** has the same gap — no mechanism to enter credentials and establish a session.
- **The `X-Admin-Key` model assumes API clients** (CLI, curl, Chrome extension), not interactive browser sessions.

## Goals

### Primary Goals

1. Provide a login page that works from any browser or mobile device
2. Protect all API endpoints behind authentication in production
3. Maintain sessions across page refreshes (cookie-based)
4. Preserve backward compatibility with `X-Admin-Key` for programmatic access
5. Work identically across all database providers (local, Supabase, Neon, Railway)
6. Rate limit login attempts (5 per IP per 15 minutes)

### Secondary Goals

1. `aca manage generate-secret` CLI command for easy key generation
2. CSRF protection via SameSite cookies

## Non-Goals

- User registration (single-user, password is configured via env var)
- Email/password authentication (no email needed)
- OAuth / social login (deferred to Phase 2)
- Multi-user data isolation (deferred to Phase 2)
- Multi-factor authentication
- Password reset flow (owner controls the env var directly)

## Approach

### Architecture

**Same-origin deployment** (recommended — reverse proxy serves both frontend and API):

```
Browser/Mobile                 FastAPI                     No DB changes
     │                           │
     │  GET /app (no session)    │
     │──────────────────────────>│
     │  302 → /login             │
     │<──────────────────────────│
     │                           │
     │  POST /api/v1/auth/login  │
     │  { password: "..." }      │
     │──────────────────────────>│
     │     verify against        │
     │     APP_SECRET_KEY        │
     │  Set-Cookie: session=JWT  │
     │  (HttpOnly, Secure,       │
     │   SameSite=Lax)           │
     │<──────────────────────────│
     │                           │
     │  GET /api/v1/digests      │
     │  Cookie: session=JWT      │
     │──────────────────────────>│
     │     verify JWT            │
     │  200 OK                   │
     │<──────────────────────────│
```

**Cross-origin deployment** (e.g., Railway with separate frontend/API services):

```
Browser/Mobile                 FastAPI
     │                           │
     │  POST /api/v1/auth/login  │
     │──────────────────────────>│
     │  Set-Cookie: session=JWT  │
     │  (HttpOnly, Secure,       │
     │   SameSite=None)          │
     │<──────────────────────────│
     │                           │
     │  GET /api/v1/digests      │
     │  Cookie: session=JWT      │  (credentials: "include")
     │──────────────────────────>│
     │  200 OK                   │
     │<──────────────────────────│
```

See "Cross-Origin Cookie Strategy" section below for details.

### Technology Stack

**Backend (Python/FastAPI):**
- `PyJWT` — JWT encoding/decoding (HS256)
- `APP_SECRET_KEY` env var — login password; JWT signing key derived via HMAC
- FastAPI middleware — checks session cookie or `X-Admin-Key` header
- `secrets.compare_digest()` — timing-safe password comparison

**Frontend (React/TanStack Router):**
- `/login` route — password-only form
- Session check via TanStack Router `beforeLoad` in `__root.tsx`
- No token storage in JavaScript — HttpOnly cookie is invisible to JS
- Cross-origin: `credentials: "include"` on all `fetch()` calls when `VITE_API_URL` is set

**Database:**
- No changes. No migrations. No user table. Stateless JWT means no sessions table.

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Credential | Single `APP_SECRET_KEY` env var | Owner-only personal tool. No user table needed. Separate from `ADMIN_API_KEY` — different purpose (login password vs API key). |
| Token format | JWT (HS256), signed with derived key | Stateless — no sessions table, no DB queries to verify. Signing key is HMAC-derived from `APP_SECRET_KEY`, so knowing the password alone doesn't allow forging tokens. |
| Token delivery | HttpOnly + Secure + SameSite cookie | Immune to XSS (JS can't read it). Works transparently with `fetch()`. `SameSite=Lax` for same-origin, `SameSite=None; Secure` for cross-origin. |
| Token lifetime | 7 days, sliding window with threshold | Personal tool — convenience matters. Cookie refreshed only when token age > 1 day (avoids rewriting cookie on every request). |
| Login UI | SPA route at `/login` via TanStack Router `beforeLoad` | Consistent with app. Prevents flash-of-content. Password-only field, no email/username. |
| API clients | `X-Admin-Key` header still works | CLI, curl, bookmarklet, Chrome extension — all unchanged. Cookie is additive. |
| Dev mode | No auth required | `ENVIRONMENT=development` bypasses auth, matching current behavior. Navigating to `/login` in dev redirects to `/`. |
| Content capture | `/api/v1/save/*` requires cookie or `X-Admin-Key` | Chrome extension and bookmarklet authenticate via `X-Admin-Key` header. Bookmarklet generator embeds the key. |
| Rate limiting | 5 attempts per IP per 15 min (in-memory) | Must-have for internet-exposed single-password login. In-memory dict, no Redis. |
| Login auditing | Log all attempts at WARNING (fail) / INFO (success) | Critical for single-user tool — owner must know if someone is probing. |

### Cross-Origin Cookie Strategy

Railway deploys frontend and backend as separate services on different origins (e.g., `aca-web.up.railway.app` and `aca-api.up.railway.app`). This affects cookie behavior:

- `SameSite=Lax` cookies are **not sent** on cross-origin `fetch()` requests — only on top-level navigations.
- `SameSite=None; Secure` cookies **are sent** cross-origin, but require HTTPS and explicit `credentials: "include"` on fetch.

**Approach: Explicit `AUTH_COOKIE_CROSS_ORIGIN` setting**

```bash
# .env — Railway split deployment (frontend ≠ backend origin)
AUTH_COOKIE_CROSS_ORIGIN=true    # Sets SameSite=None; Secure

# .env — Same-origin deployment (default)
AUTH_COOKIE_CROSS_ORIGIN=false   # Sets SameSite=Lax (default)
```

The deployer knows their topology. Auto-detection was considered (comparing `ALLOWED_ORIGINS` against the API's own host) but rejected — the backend doesn't have a canonical `api_base_url` setting, and deriving it from request headers is fragile behind proxies. An explicit boolean is simpler and more reliable.

**Frontend side:**
- When `VITE_API_URL` is set (cross-origin), the API client adds `credentials: "include"` to all fetch requests. This is set globally on the fetch wrapper — harmless for unauthenticated endpoints (cookies are simply absent or ignored).
- When `VITE_API_URL` is unset (same-origin via proxy), cookies are sent automatically with `credentials: "same-origin"`.

**CORS requirements for cross-origin cookies:**
- `Access-Control-Allow-Credentials: true` (already set in `app.py`)
- `Access-Control-Allow-Origin` must be the specific origin, **not** `*` (already handled — CORS middleware uses explicit origins list)

### Endpoint Protection

After this change, the authentication model shifts from "some endpoints protected" to "all endpoints protected, some exempted":

| Endpoint | Auth | Reason |
|---|---|---|
| `/health`, `/ready` | None | Infrastructure probes |
| `/api/v1/system/config` | None | Frontend feature flags (no sensitive data) |
| `/api/v1/otel/v1/traces` | None | Frontend OTLP proxy |
| `/api/v1/auth/*` | None | Login/logout/session endpoints |
| `/docs`, `/redoc`, `/openapi.json` | Session cookie OR `X-Admin-Key` | Protected — API schema visible only after login |
| `/login` (frontend) | None | Login page must be accessible |
| **All other endpoints** | Session cookie OR `X-Admin-Key` | Authenticated access required (includes SSE/streaming endpoints — auth checked before streaming begins) |

**Note on frontend assets:** The backend does NOT serve static files (no `StaticFiles` mount). Frontend assets (PWA manifest, service worker, icons) are served by the frontend service (Vite in dev, separate Railway service in production). The auth middleware only runs on FastAPI routes, so no frontend asset exemptions are needed.

### JWT Signing Key Derivation

The `APP_SECRET_KEY` serves as the login password. The JWT signing key is **derived** from it, not used directly:

```python
import hmac

def get_jwt_signing_key(app_secret_key: str) -> bytes:
    """Derive JWT signing key from the app secret.

    Separates the password (what the user types) from the signing key
    (what proves token authenticity). Knowing the password alone does
    not allow forging tokens without also knowing this derivation.
    """
    return hmac.new(
        app_secret_key.encode(), b"jwt-signing-key", "sha256"
    ).digest()
```

This means:
- Shoulder-surfing the password doesn't allow forging JWTs
- The signing key is deterministic (no extra state to manage)
- Changing `APP_SECRET_KEY` invalidates all existing sessions (desired behavior)

### Security Considerations

1. **Password verification**: `secrets.compare_digest()` — timing-safe comparison
2. **JWT signing**: HS256 with HMAC-derived key (not raw password). Min 32-character `APP_SECRET_KEY` recommended.
3. **Cookie security**: `HttpOnly` (no JS access), `Secure` (HTTPS only in production), `SameSite=Lax` (default) or `SameSite=None` (when `AUTH_COOKIE_CROSS_ORIGIN=true`)
4. **No password in JWT**: Token payload contains only `iss`, `iat`, `exp` — no secrets
5. **Sliding window with threshold**: Cookie refreshed only when `now - iat > 1 day`. Expires after 7 days of inactivity. Avoids rewriting cookie on every request.
6. **Rate limiting**: 5 failed login attempts per IP = 15-minute lockout. In-memory dict with TTL cleanup. Prevents brute-force.
7. **Login auditing**: Failed attempts logged at WARNING with client IP. Successful logins logged at INFO.
8. **Dev mode bypass**: Development environment skips auth entirely (unchanged from today). Navigating to `/login` in dev mode redirects to `/`.
9. **Graceful degradation**: If `APP_SECRET_KEY` is not set in production, log a warning and fall back to `ADMIN_API_KEY`-only protection (backward compatible).
10. **SSE/streaming**: Auth middleware checks credentials before the streaming generator begins — no data is sent to unauthenticated clients.
11. **Session revocation**: Changing `APP_SECRET_KEY` invalidates all existing sessions immediately (HMAC-derived signing key changes). This is the only revocation mechanism — there is no per-session or per-device revocation (stateless JWT trade-off). To force re-login on all devices, rotate the key.
12. **Proxy headers**: Uvicorn must run with `--proxy-headers --forwarded-allow-ips='*'` when behind a reverse proxy (Railway, any load balancer). Without this, `request.client.host` returns the proxy IP, and the rate limiter tracks a single IP for all clients — locking out everyone after 5 failed attempts from anyone.
13. **Error response format**: Auth error responses (`401`, `403`, `429`) use the same JSON structure as the existing error handler middleware: `{"error": "...", "detail": "...", "trace_id": "..."}`. This ensures the frontend `ApiClientError` parser works uniformly.

### Configuration

```yaml
# profiles/base.yaml — add to settings section
settings:
  app_secret_key: "${APP_SECRET_KEY:-}"
  auth_cookie_cross_origin: "${AUTH_COOKIE_CROSS_ORIGIN:-false}"

# .secrets.yaml
APP_SECRET_KEY: your-strong-random-password

# Or .env
APP_SECRET_KEY=your-strong-random-password
AUTH_COOKIE_CROSS_ORIGIN=false          # true for Railway split deployments
```

**Generate a secure key:**
```bash
aca manage generate-secret          # prints a 64-char random key
# or manually:
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Behavior matrix:**

| `APP_SECRET_KEY` | `ADMIN_API_KEY` | Environment | Result |
|---|---|---|---|
| Set | Set | Production | Full auth: login page + API key both work |
| Set | Not set | Production | Login page works, no API key fallback |
| Not set | Set | Production | Warning logged, `X-Admin-Key`-only protection (backward compat) |
| Not set | Not set | Production | Warning logged, all protected endpoints return 500 |
| Any | Any | Development | No auth required (unchanged) |

## Implementation Plan

See `tasks.md` for the detailed task breakdown.

**Summary:**
1. Backend auth endpoints, middleware, and rate limiting (~400 lines, 4 files)
2. Frontend login page and session check (~200 lines, 3 files)
3. Configuration integration (settings + profiles + CLI)
4. Testing (backend unit + E2E)

## Success Criteria

### Must Have

- [ ] Login page accessible at `/login` on deployed instances
- [ ] Password verified against `APP_SECRET_KEY` env var
- [ ] JWT signing key derived via HMAC (not raw password)
- [ ] Session persists across page refreshes (7-day HttpOnly cookie)
- [ ] All API endpoints protected in production (except exempted)
- [ ] Works for both same-origin and cross-origin deployments (`AUTH_COOKIE_CROSS_ORIGIN` setting)
- [ ] `X-Admin-Key` header continues to work for CLI/extension access
- [ ] Rate limiting on login: 5 attempts / 15 min per IP
- [ ] Failed login attempts logged with client IP
- [ ] Development mode requires no auth (unchanged)
- [ ] Backend tests pass (login, logout, session, middleware, rate limiting)
- [ ] E2E tests pass (login flow, protected routes, session persistence)

### Nice to Have

- [ ] `aca manage generate-secret` CLI command
- [ ] Startup warning if `APP_SECRET_KEY` < 32 characters

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| `APP_SECRET_KEY` too short/weak | Critical | Medium | Log warning on startup if < 32 chars. Provide `generate-secret` CLI command. Document in setup guide. |
| Cookie not sent cross-origin | High | Medium | Explicit `AUTH_COOKIE_CROSS_ORIGIN=true` sets `SameSite=None`. Frontend uses `credentials: "include"` when `VITE_API_URL` is set. |
| JWT token theft (cookie stolen) | Critical | Very Low | HttpOnly prevents XSS extraction. Secure flag prevents HTTP sniffing. 7-day expiry limits window. HMAC derivation limits damage of password-only leak. |
| Brute-force login attempts | High | Medium | In-memory rate limiter: 5 attempts per IP per 15 min. Failed attempts logged. |
| Breaking existing `X-Admin-Key` workflows | High | Low | Both auth methods coexist. Middleware checks cookie first, then header. |
| Dev mode accidentally deployed | Medium | Low | Startup logs auth mode prominently. |
| SSE streams data before auth check | Medium | Low | Middleware runs before route handler — auth enforced before streaming begins. Test explicitly. |

## Dependencies

**External:**
- `PyJWT` Python package (add to `pyproject.toml`)

**Internal:**
- `src/config/settings.py` — add `app_secret_key` and `auth_cookie_cross_origin` fields
- `profiles/base.yaml` — add settings with `${APP_SECRET_KEY:-}` and `${AUTH_COOKIE_CROSS_ORIGIN:-false}` references
- `web/src/lib/api/client.ts` — add `credentials: "include"` when `VITE_API_URL` is set
- `Dockerfile` — add `--proxy-headers --forwarded-allow-ips='*'` to uvicorn command
- `Makefile` — add `--proxy-headers` to dev uvicorn command

## Future: Phase 2 (Multi-User)

This proposal intentionally avoids multi-user complexity. If multi-user is needed later, Phase 2 adds an `AuthProvider` abstraction (see `design.md`):

- `owner` provider — this Phase 1 implementation (default)
- `supabase` provider — delegate to Supabase GoTrue (email/password, OAuth)
- `self-hosted` provider — users table + Argon2 hashing

Phase 2 also requires `user_id` foreign keys on content tables and per-user query scoping — a significant migration that should only happen when there's a concrete second user.

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [JWT Best Practices (RFC 8725)](https://tools.ietf.org/html/rfc8725)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- `design.md` — Full two-phase authentication strategy design

---

**Created**: 2026-01-12
**Updated**: 2026-02-20
**Proposal ID**: add-user-authentication
**Status**: Ready for Implementation (Phase 1)
