# Authentication Strategy Design

> **Updated**: 2026-02-20 — Aligned with current Python/FastAPI stack and provider architecture

## Problem Statement

The app currently uses `ADMIN_API_KEY` (via `X-Admin-Key` header) to protect settings/prompt endpoints, with all content endpoints open under a single-user model. This works for local development but breaks down when the app is deployed to the cloud and accessed from a mobile device or browser:

1. **Browsers can't send custom headers** without JavaScript — there's no login page, so a user visiting the deployed app sees everything unprotected or has no way to authenticate.
2. **Mobile/PWA access** has the same problem — no mechanism to enter credentials and establish a session.
3. **The `X-Admin-Key` model assumes CLI/API clients**, not interactive browser sessions.

### What we actually need

A way for the app owner (and potentially invited users) to **log in via a browser**, get a session, and have all API requests authenticated transparently — while keeping the deployment simple across all three database providers (local Docker, Supabase, Neon, Railway).

---

## Current State

### Auth today (`src/api/dependencies.py`)

| Endpoint pattern | Auth | Reason |
|---|---|---|
| `/api/v1/settings/*`, `/api/v1/prompts/*`, `/api/v1/contents/*` | `X-Admin-Key` header | Admin operations |
| `/api/v1/digests/*`, `/api/v1/chat/*`, etc. (18+ routes) | None | Single-user model |
| `/health`, `/ready`, `/api/v1/system/config` | None | Infrastructure |

### Database provider auth capabilities

| Provider | Built-in auth? | Details |
|---|---|---|
| **Supabase** | Yes — GoTrue / `auth-py` SDK | Full auth service: email/password, OAuth (Google, GitHub), JWT, RLS. Python SDK available (`supabase-auth` 2.27.x). Auth data lives in managed schema. |
| **Neon** | Yes — Neon Auth (Better Auth) | Rebuilt Dec 2025 on Better Auth. Auth data in `neon_auth` schema, branch-aware. **But SDK is JavaScript/Next.js focused** — no official Python client. |
| **Railway** | No | Just PostgreSQL. No auth service. Need self-hosted auth. |
| **Local Docker** | No | Development environment. |

### Key insight

Neon Auth's lack of a Python SDK and Railway's lack of any auth service means **we can't rely on database-provider auth as the universal solution**. We need something that works everywhere, with optional enhancement when a managed auth service is available.

---

## Recommendation: Two-Phase Approach

### Phase 1 — "Owner Auth" (Single-User, All Providers)

A minimal, self-contained authentication layer that solves the immediate problem: **browser/mobile access to a cloud-deployed instance**.

#### How it works

```
Browser                    FastAPI                    Database
  │                          │                          │
  │  GET /app (no session)   │                          │
  │─────────────────────────>│                          │
  │  302 → /login            │                          │
  │<─────────────────────────│                          │
  │                          │                          │
  │  POST /api/v1/auth/login │                          │
  │  { password: "..." }     │                          │
  │─────────────────────────>│                          │
  │       verify against     │                          │
  │       APP_SECRET_KEY     │                          │
  │  Set-Cookie: session=JWT │                          │
  │  (HttpOnly, Secure,      │                          │
  │   SameSite=Lax)          │                          │
  │<─────────────────────────│                          │
  │                          │                          │
  │  GET /api/v1/digests     │                          │
  │  Cookie: session=JWT     │                          │
  │─────────────────────────>│                          │
  │       verify JWT         │                          │
  │  200 OK                  │                          │
  │<─────────────────────────│                          │
```

#### Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Credential | Single password (`APP_SECRET_KEY` env var) | Owner-only tool. No user table needed. Falls back to `ADMIN_API_KEY` if `APP_SECRET_KEY` not set, preserving backward compatibility. |
| Token format | JWT (HS256, signed with HMAC-derived key) | Stateless — no sessions table needed. Signing key derived from password via HMAC so knowing the password alone doesn't allow forging tokens. |
| Token delivery | HttpOnly Secure SameSite cookie | Immune to XSS (JavaScript can't read it). `SameSite=Lax` by default; `SameSite=None` when `AUTH_COOKIE_CROSS_ORIGIN=true` (Railway split deployments). |
| Token lifetime | 7 days, sliding window (1-day threshold) | Personal tool — convenience over strict expiry. Cookie refreshed only when token > 1 day old (avoids rewriting on every request). |
| Login UI | SPA route at `/login` via TanStack Router `beforeLoad` | Prevents flash-of-content. No username/email needed. Redirects to `/` in dev mode. |
| API clients | `X-Admin-Key` header still works | CLI, curl, bookmarklet, Chrome extension — all keep working. Cookie auth is additive, not a replacement. |
| Dev mode | No auth required (unchanged) | `ENVIRONMENT=development` bypasses auth like today. |
| Rate limiting | 5 attempts / IP / 15 min (in-memory) | Must-have for internet-exposed single-password login. No Redis needed. |
| Login auditing | WARNING on failure, INFO on success (with IP) | Critical for owner to detect probing attempts. |

#### What changes

**Backend** (~400 lines):
- `src/api/auth_routes.py` — `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/session`
- `src/api/middleware/auth.py` — middleware that checks cookie OR `X-Admin-Key` header on every request (except `/health`, `/ready`, `/login`, `/api/v1/auth/*`, static assets)
- `src/api/rate_limiter.py` — in-memory rate limiter (5 attempts / IP / 15 min)
- `src/config/settings.py` — add `app_secret_key` field
- `pyproject.toml` — add `PyJWT` dependency

**Frontend** (~200 lines):
- `web/src/routes/login.tsx` — password form
- `web/src/lib/api/auth.ts` — `checkSession()`, `login()`, `logout()`
- `web/src/lib/api/client.ts` — add `credentials: "include"` for cross-origin
- `web/src/routes/__root.tsx` — `beforeLoad` session check (prevents flash-of-content)

**No database changes. No migrations. No user table.**

#### Configuration

```yaml
# profiles/base.yaml (add to settings)
settings:
  app_secret_key: "${APP_SECRET_KEY:-}"

# .secrets.yaml
APP_SECRET_KEY: your-strong-random-password

# Or just .env
APP_SECRET_KEY=your-strong-random-password
```

When `APP_SECRET_KEY` is not set:
- **Development**: No auth (like today)
- **Production**: Log a warning, fall back to `ADMIN_API_KEY` for backward compat. If neither is set, all protected endpoints return 500.

---

### Phase 2 — Auth Provider Abstraction (Multi-User, Optional)

If/when multi-user support is needed (e.g., sharing a deployed instance with a team), introduce an auth provider abstraction that mirrors the existing `DatabaseProvider` pattern.

#### Provider interface

```python
class AuthProvider(ABC):
    """Authentication provider interface."""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> AuthResult:
        """Verify credentials, return user info + tokens."""

    @abstractmethod
    async def verify_token(self, token: str) -> UserInfo | None:
        """Verify a session token, return user info or None."""

    @abstractmethod
    async def logout(self, token: str) -> None:
        """Invalidate a session."""

    @property
    @abstractmethod
    def supports_registration(self) -> bool:
        """Whether this provider allows new user registration."""
```

#### Provider implementations

| Provider | `AUTH_PROVIDER` | When to use |
|---|---|---|
| `owner` (default) | Phase 1 password auth | Single-user, any DB provider |
| `supabase` | Supabase GoTrue via `auth-py` | Supabase deployments wanting managed auth |
| `self-hosted` | FastAPI + SQLAlchemy users table | Railway/local wanting multi-user without external auth |

#### Supabase Auth provider

When `AUTH_PROVIDER=supabase`:
- Login/registration delegated to Supabase Auth (email/password, OAuth)
- Backend verifies Supabase-issued JWTs using the project's JWT secret
- User data lives in Supabase's `auth.users` schema
- RLS policies can gate data per-user at the database level
- Python integration via `supabase-auth` SDK or direct JWT verification with `python-jose`

#### Self-hosted provider

When `AUTH_PROVIDER=self-hosted`:
- `users` table in application DB (id, email, password_hash, role, created_at)
- Password hashing via `argon2-cffi` (modern, memory-hard — better than bcrypt)
- JWT issued by the app, verified by the app
- Invitation-only registration (owner sends invite link)

#### What Phase 2 adds on top of Phase 1

- User model + migration
- Registration endpoint (if provider supports it)
- Per-user data isolation (user_id FK on content tables + migration)
- Auth provider factory (like `src/storage/providers/factory.py`)
- Profile integration (`providers.auth: supabase | self-hosted | owner`)
- Frontend: login form expands to email+password, optional registration page

---

## Single-User vs Multi-User: Complexity Comparison

| Aspect | Phase 1 (Owner Auth) | Phase 2 (Multi-User) |
|---|---|---|
| Database changes | None | User table, user_id FK on ~10 tables, migrations |
| Backend code | ~300 lines (3 files) | ~800-1000 lines (auth provider abstraction, registration, invitations, user CRUD) |
| Frontend code | ~200 lines (login page + session check) | ~600-800 lines (registration, user profile, invitation acceptance, auth context) |
| Configuration | 1 env var (`APP_SECRET_KEY`) | Auth provider config, potentially Supabase keys, SMTP for invitations |
| Data model impact | Zero — no schema changes | Every content table needs `user_id`, all queries need user scoping |
| Testing | Minimal — login/logout + middleware | Significant — per-user isolation, cross-user access prevention, provider matrix |

**Recommendation**: Phase 1 is the right starting point. It solves the actual problem (cloud access from browser/mobile) with minimal complexity. Phase 2 should only be built if there's a concrete need for multiple users — the data model changes are significant and shouldn't be speculative.

---

## Answering Your Specific Questions

### "How should ADMIN_API_KEY be provided when accessing via mobile/browser?"

It shouldn't — that's the wrong abstraction for browsers. Phase 1 replaces the browser auth story with a login page + session cookie while keeping `X-Admin-Key` working for programmatic access. The two coexist:

- **Browser/mobile**: Login page → cookie
- **CLI/curl/extensions**: `X-Admin-Key` header (unchanged)

### "Supabase and Neon have auth — should we use them?"

- **Supabase Auth**: Yes, but only as a Phase 2 option. It has a mature Python SDK and would be the natural choice for Supabase deployments wanting multi-user. However, it can't be the *only* auth strategy because Railway and local deployments don't have it.
- **Neon Auth**: Not viable as a primary auth strategy. The SDK is JavaScript-only (Next.js focused). It's interesting for Neon-deployed apps with a JS backend, but doesn't fit our Python/FastAPI stack. If this changes (Python SDK released), it could become another Phase 2 provider.

### "For Railway, do we need to add an auth component?"

Yes. Railway gives you PostgreSQL and nothing else — no managed auth. Phase 1's owner-auth works out of the box on Railway (just set `APP_SECRET_KEY`). For Phase 2 multi-user on Railway, use the self-hosted provider (users table in your Railway PostgreSQL).

### "How complex is multi-user vs single-user?"

See the comparison table above. The real complexity isn't in auth itself — it's in **data isolation**. Every query currently assumes single-user. Making it multi-user means adding `user_id` to content, summaries, digests, chat conversations, etc., and scoping every query. That's a significant migration and a pervasive code change.

For a personal content management tool, this is premature. Build it when you have a second user.

---

## Migration Path (Existing Proposal → This Design)

The existing proposal in `openspec/changes/add-user-authentication/proposal.md` should be updated:

1. **Drop**: Node.js/Express/Passport.js/bcrypt references
2. **Drop**: Username support, complex registration flows (Phase 1 doesn't need them)
3. **Keep**: Security considerations (rate limiting, HTTPS, CSRF) — apply to Phase 2
4. **Keep**: OAuth as a Phase 2 secondary goal (via Supabase Auth provider)
5. **Add**: Provider abstraction pattern matching existing codebase architecture
6. **Add**: Cookie-based auth (proposal only mentioned JWT in Authorization header)
7. **Add**: Backward compatibility with `X-Admin-Key`

---

## Resolved Design Decisions

These were open questions during the initial design discussion. All have been resolved:

1. **Phase 1 password is separate from `ADMIN_API_KEY`** — new `APP_SECRET_KEY` env var. Admin key is an API concept; login password is a user concept. Both coexist.

2. **Login page is an SPA route** (`/login`) — consistent with app, uses TanStack Router `beforeLoad` to prevent flash-of-content. In dev mode, `/login` redirects to `/`.

3. **All endpoints protected** (except infrastructure probes, system config, OTLP proxy, and auth endpoints). `/api/v1/save/*` requires cookie or `X-Admin-Key` — Chrome extension and bookmarklet authenticate via header.

4. **Sliding window with 1-day threshold** — cookie only refreshed when token > 1 day old (not on every request). Avoids rewriting `Set-Cookie` on every API call. 7-day expiry on inactivity.

5. **JWT signing key is HMAC-derived** from `APP_SECRET_KEY` — knowing the password doesn't allow forging tokens. `hmac.new(key, b"jwt-signing-key", "sha256").digest()`.

6. **Rate limiting is P0** — 5 failed attempts per IP per 15 min. In-memory, no Redis. Single-password login must not be brute-forceable.

7. **Cross-origin cookies via explicit `AUTH_COOKIE_CROSS_ORIGIN` setting** — `false` (default) → `SameSite=Lax`, `true` → `SameSite=None; Secure` for Railway split deployments. Auto-detection was rejected (backend has no canonical `api_base_url` field — the deployer knows their topology). Frontend adds `credentials: "include"` when `VITE_API_URL` is set.

8. **Failed login attempts logged at WARNING with client IP** — critical for single-user tool to detect probing. Successful logins logged at INFO.

9. **Session revocation = key rotation** — changing `APP_SECRET_KEY` invalidates all sessions (HMAC-derived signing key changes). No per-device revocation (stateless JWT trade-off). Acceptable for single-user.

10. **Proxy headers required** — uvicorn must run with `--proxy-headers` behind Railway or any reverse proxy. Without it, rate limiter sees the proxy IP and locks out all users after 5 failures from anyone.

11. **OpenAPI docs protected** — `/docs`, `/redoc`, `/openapi.json` are behind auth like all other endpoints. API schema visible only after login.

12. **Error responses match existing format** — auth errors use `{"error": "...", "detail": "...", "trace_id": "..."}` to work with the frontend `ApiClientError` parser.
