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

### Secondary Goals

1. Rate limiting on login attempts
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

### Technology Stack

**Backend (Python/FastAPI):**
- `PyJWT` — JWT encoding/decoding (HS256)
- `APP_SECRET_KEY` env var — both the login password and the JWT signing key
- FastAPI middleware — checks session cookie or `X-Admin-Key` header
- `secrets.compare_digest()` — timing-safe password comparison

**Frontend (React/TanStack Router):**
- `/login` route — password-only form
- Session check in `__root.tsx` — redirect to `/login` if unauthenticated
- No token storage in JavaScript — HttpOnly cookie is invisible to JS

**Database:**
- No changes. No migrations. No user table. Stateless JWT means no sessions table.

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Credential | Single `APP_SECRET_KEY` env var | Owner-only personal tool. No user table needed. Separate from `ADMIN_API_KEY` — different purpose (login password vs API key). |
| Token format | JWT (HS256), signed with `APP_SECRET_KEY` | Stateless — no sessions table, no DB queries to verify. |
| Token delivery | HttpOnly + Secure + SameSite=Lax cookie | Immune to XSS (JS can't read it). Works transparently with `fetch()`. No localStorage token management. |
| Token lifetime | 7 days, sliding window | Personal tool — convenience matters. Each authenticated request refreshes the expiry. |
| Login UI | SPA route at `/login` | Consistent with app. Password-only field, no email/username. |
| API clients | `X-Admin-Key` header still works | CLI, curl, bookmarklet, Chrome extension — all unchanged. Cookie is additive. |
| Dev mode | No auth required | `ENVIRONMENT=development` bypasses auth, matching current behavior. |
| Content capture | `/api/v1/save/*` accepts both cookie and `X-Admin-Key` | Chrome extension and bookmarklet keep working via header. |

### Endpoint Protection

After this change, the authentication model shifts from "some endpoints protected" to "all endpoints protected, some exempted":

| Endpoint | Auth | Reason |
|---|---|---|
| `/health`, `/ready` | None | Infrastructure probes |
| `/api/v1/system/config` | None | Frontend feature flags (no sensitive data) |
| `/api/v1/otel/v1/traces` | None | Frontend OTLP proxy |
| `/api/v1/auth/*` | None | Login/logout/session endpoints |
| `/login` (frontend) | None | Login page must be accessible |
| **All other endpoints** | Session cookie OR `X-Admin-Key` | Authenticated access required |

### Security Considerations

1. **Password verification**: `secrets.compare_digest()` — timing-safe comparison
2. **JWT signing**: HS256 with `APP_SECRET_KEY` as the secret (min 32 characters recommended)
3. **Cookie security**: `HttpOnly` (no JS access), `Secure` (HTTPS only in production), `SameSite=Lax` (CSRF mitigation)
4. **No password in JWT**: Token payload contains only `iss`, `iat`, `exp` — no secrets
5. **Sliding window expiry**: Token refreshed on each request, expires after 7 days of inactivity
6. **Rate limiting** (secondary goal): 5 failed attempts per IP = 15-minute lockout
7. **Dev mode bypass**: Development environment skips auth entirely (unchanged from today)
8. **Graceful degradation**: If `APP_SECRET_KEY` is not set in production, log a warning and fall back to `ADMIN_API_KEY`-only protection (backward compatible)

### Configuration

```yaml
# profiles/base.yaml — add to settings section
settings:
  app_secret_key: "${APP_SECRET_KEY:-}"

# .secrets.yaml
APP_SECRET_KEY: your-strong-random-password

# Or .env
APP_SECRET_KEY=your-strong-random-password
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
1. Backend auth endpoints and middleware (~300 lines, 3 files)
2. Frontend login page and session check (~200 lines, 3 files)
3. Configuration integration (settings + profiles)
4. Testing (backend unit + E2E)

## Success Criteria

### Must Have

- [ ] Login page accessible at `/login` on deployed instances
- [ ] Password verified against `APP_SECRET_KEY` env var
- [ ] Session persists across page refreshes (7-day HttpOnly cookie)
- [ ] All API endpoints protected in production (except exempted)
- [ ] `X-Admin-Key` header continues to work for CLI/extension access
- [ ] Development mode requires no auth (unchanged)
- [ ] Backend tests pass (login, logout, session, middleware)
- [ ] E2E tests pass (login flow, protected routes, session persistence)

### Nice to Have

- [ ] Rate limiting on `/api/v1/auth/login` (5 attempts / 15 min)
- [ ] `GET /api/v1/auth/session` returns auth status for frontend
- [ ] Logout clears cookie and redirects to `/login`

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| `APP_SECRET_KEY` too short/weak | Critical | Medium | Log warning on startup if < 32 chars. Document in setup guide. |
| Cookie not sent cross-origin | High | Low | `SameSite=Lax` allows top-level navigation. Same-origin deployment (API + frontend) avoids this. |
| JWT token theft (cookie stolen) | Critical | Very Low | HttpOnly prevents XSS extraction. Secure flag prevents HTTP sniffing. 7-day expiry limits window. |
| Breaking existing `X-Admin-Key` workflows | High | Low | Both auth methods coexist. Middleware checks cookie first, then header. |
| Dev mode accidentally deployed | Medium | Low | Startup logs auth mode prominently. |

## Dependencies

**External:**
- `PyJWT` Python package (add to `pyproject.toml`)

**Internal:**
- `src/config/settings.py` — add `app_secret_key` field
- `profiles/base.yaml` — add `app_secret_key` setting with `${APP_SECRET_KEY:-}` reference

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
