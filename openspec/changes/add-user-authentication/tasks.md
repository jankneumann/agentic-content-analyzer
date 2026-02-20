# Implementation Tasks: Owner Authentication (Phase 1)

## Task 1.1: Add `APP_SECRET_KEY` to Settings and Profiles

**Priority**: P0 (Blocker)
**Estimate**: 1 hour
**Dependencies**: None

### Description

Add the `app_secret_key` field to the Settings model and wire it into the profile system. Add a `generate-secret` management command.

### Acceptance Criteria

- [ ] `app_secret_key: str | None` field added to `Settings` in `src/config/settings.py`
- [ ] `app_secret_key: "${APP_SECRET_KEY:-}"` added to `profiles/base.yaml` under `settings`
- [ ] Startup validator logs warning if `APP_SECRET_KEY` not set in production (like `admin_api_key`)
- [ ] Startup validator logs warning if key is < 32 characters
- [ ] `aca manage generate-secret` command prints a cryptographically random 64-char key (uses `secrets.token_urlsafe(48)`)
- [ ] Existing `ADMIN_API_KEY` behavior unchanged
- [ ] Tests pass with `_env_file=None` (no pickup from `.env`)

### Files Changed

- `src/config/settings.py` — add field + startup validation in `validate_production_security()`
- `profiles/base.yaml` — add `app_secret_key` reference
- `src/cli/manage.py` (or equivalent) — add `generate-secret` subcommand

### Testing

- Settings loads with `APP_SECRET_KEY` from env
- Settings loads without `APP_SECRET_KEY` (None, no crash)
- Warning logged when missing in production
- Warning logged when key < 32 chars
- `generate-secret` outputs a valid key of correct length

---

## Task 1.2: Create Auth Endpoints

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 1.1

### Description

Create `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/session` endpoints. JWT signing key is HMAC-derived from `APP_SECRET_KEY` (not used directly).

### Acceptance Criteria

- [ ] `POST /api/v1/auth/login` accepts `{ "password": "..." }`
- [ ] Password verified with `secrets.compare_digest()` against `APP_SECRET_KEY`
- [ ] JWT signing key derived via `hmac.new(key, b"jwt-signing-key", "sha256").digest()` — never use raw password as signing key
- [ ] On success: returns 200 with `Set-Cookie: session=<JWT>` (HttpOnly, Secure in production, SameSite auto-detected, Max-Age=604800, Path=/)
- [ ] On failure: returns 401 `{ "error": "Invalid credentials" }`
- [ ] Failed login logged at WARNING with client IP: `"Failed login attempt from %s"`
- [ ] Successful login logged at INFO: `"Successful login from %s"`
- [ ] JWT payload: `{ "iss": "newsletter-aggregator", "iat": <unix>, "exp": <unix+7d> }`
- [ ] `POST /api/v1/auth/logout` clears the session cookie (Set-Cookie with Max-Age=0)
- [ ] `GET /api/v1/auth/session` returns `{ "authenticated": true/false }` based on valid cookie
- [ ] SameSite auto-detection: `Lax` when all allowed origins share the API host, `None` when cross-origin origins detected (see proposal "Cross-Origin Cookie Strategy")
- [ ] Auth router registered in `src/api/app.py`
- [ ] `PyJWT` added to `pyproject.toml` dependencies

### Request/Response Formats

```python
# POST /api/v1/auth/login
# Request body:
{"password": "the-app-secret"}

# Success (200) — body:
{"authenticated": true}
# + Set-Cookie header with JWT

# Failure (401) — body:
{"error": "Invalid credentials"}

# Rate limited (429) — body:
{"error": "Too many login attempts. Try again in N minutes."}

# POST /api/v1/auth/logout
# Success (200) — body:
{"authenticated": false}
# + Set-Cookie clearing the session

# GET /api/v1/auth/session
# Authenticated (200):
{"authenticated": true}
# Not authenticated (200):
{"authenticated": false}
```

### Files Changed

- `src/api/auth_routes.py` — new file, auth router
- `src/api/app.py` — register auth router
- `pyproject.toml` — add `PyJWT` dependency

### Testing

- Login with correct password returns 200 + cookie
- Login with wrong password returns 401 + WARNING log with IP
- Successful login emits INFO log with IP
- Login with empty password returns 401 (or 422)
- Login when `APP_SECRET_KEY` not set returns 500
- Logout clears session cookie
- Session endpoint returns status based on cookie validity
- JWT expiry is 7 days from login
- JWT signed with HMAC-derived key (not raw password)
- Cookie flags correct (HttpOnly, SameSite, Path=/)
- Secure flag only set when not in development
- SameSite=None when cross-origin origins in ALLOWED_ORIGINS
- SameSite=Lax when same-origin only

---

## Task 1.3: Create Rate Limiter

**Priority**: P0 (Blocker)
**Estimate**: 2 hours
**Dependencies**: Task 1.2

### Description

In-memory rate limiter for the login endpoint. No Redis or external dependencies. Tracks failed attempts per client IP with automatic expiry.

### Acceptance Criteria

- [ ] 5 failed login attempts per IP within 15 minutes triggers lockout
- [ ] Locked-out IPs receive 429 with `Retry-After` header and human-readable message
- [ ] Successful login does NOT reset the counter (prevents timing attacks)
- [ ] Counter entries expire after 15 minutes (TTL-based cleanup)
- [ ] Cleanup runs periodically (e.g., every 100 requests) to prevent unbounded memory growth
- [ ] Rate limiter is a standalone module (reusable for Phase 2 if needed)
- [ ] Thread-safe (FastAPI may use multiple workers — per-process is acceptable for Phase 1)
- [ ] Trusts `X-Forwarded-For` only when behind a trusted proxy (configurable)

### Implementation Notes

```python
# src/api/rate_limiter.py
from collections import defaultdict
from time import monotonic

class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._max = max_attempts
        self._window = window_seconds

    def is_blocked(self, ip: str) -> bool:
        """Check if IP is blocked. Prunes expired entries."""
        ...

    def record_failure(self, ip: str) -> None:
        """Record a failed login attempt."""
        ...

    def get_retry_after(self, ip: str) -> int:
        """Seconds until the IP can retry."""
        ...
```

### Files Changed

- `src/api/rate_limiter.py` — new file, standalone rate limiter

### Testing

- 5 failures from same IP → 6th attempt blocked with 429
- Different IPs tracked independently
- Entries expire after 15 minutes (use time mocking)
- Cleanup doesn't affect unexpired entries
- Memory doesn't grow unbounded under sustained attack simulation

---

## Task 1.4: Create Auth Middleware

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 1.2

### Description

Create FastAPI middleware that enforces authentication on all endpoints except explicitly exempted ones. Supports both session cookies (browser) and `X-Admin-Key` headers (programmatic). Implements sliding window with threshold.

### Acceptance Criteria

- [ ] Middleware checks for `session` cookie first, then `X-Admin-Key` header
- [ ] Valid JWT in cookie: request proceeds. If token `iat` is > 1 day old, cookie refreshed with new JWT (sliding window with threshold — avoids rewriting on every request)
- [ ] Valid `X-Admin-Key` header: request proceeds (backward compat)
- [ ] Neither present in production: returns 401
- [ ] Exempted paths skip auth entirely: `/health`, `/ready`, `/api/v1/system/config`, `/api/v1/otel/v1/traces`, `/api/v1/auth/*`
- [ ] Development mode (`ENVIRONMENT=development`): all requests pass (unchanged behavior)
- [ ] Middleware registered in `src/api/app.py` (before route registration)
- [ ] Existing `verify_admin_key` dependency on settings/prompts/contents routes unchanged (defense in depth)
- [ ] `ENDPOINT_AUTH_MAP` in `dependencies.py` updated to reflect new auth model
- [ ] SSE/streaming endpoints: auth checked before generator starts (no data leaks to unauthenticated clients)

### Exempted Paths

```python
AUTH_EXEMPT_PATHS = [
    "/health",
    "/ready",
    "/api/v1/system/config",
    "/api/v1/otel/v1/traces",
    "/api/v1/auth/",           # All auth endpoints (login, logout, session)
]
```

### Sliding Window with Threshold

```python
# On each authenticated request with a valid cookie:
# 1. Decode JWT (verify signature + expiry)
# 2. Check iat claim: if (now - iat) > 1 day:
#    a. Issue new JWT with refreshed iat + exp
#    b. Set updated cookie on response
# 3. If (now - iat) <= 1 day: no cookie refresh (save bandwidth)
# Result: session only expires after 7 days of inactivity,
#         cookie only rewritten at most once per day
```

### Files Changed

- `src/api/middleware/auth.py` — new file, auth middleware
- `src/api/app.py` — register middleware
- `src/api/dependencies.py` — update `ENDPOINT_AUTH_MAP` documentation

### Testing

- Request with valid cookie proceeds
- Request with expired cookie returns 401
- Request with valid `X-Admin-Key` proceeds (no cookie needed)
- Request with neither returns 401 in production
- Request to exempted path proceeds without auth
- Cookie refreshed when token > 1 day old
- Cookie NOT refreshed when token < 1 day old
- Development mode bypasses all auth
- Invalid JWT signature returns 401
- Tampered JWT returns 401
- JWT signed with raw password (not HMAC-derived key) returns 401
- SSE endpoint: unauthenticated request returns 401 before any streaming data

---

## Task 2.1: Create Login Page

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 1.2

### Description

Create a `/login` route in the React frontend with a password-only form.

### Acceptance Criteria

- [ ] `/login` route registered in TanStack Router
- [ ] Password input field (type="password") with submit button
- [ ] Form submits `POST /api/v1/auth/login` with `{ password }` body
- [ ] On success (200): redirect to `/` (or `returnTo` query param if present)
- [ ] On failure (401): show "Invalid password" error message
- [ ] On rate limit (429): show "Too many attempts" with retry countdown
- [ ] Loading state during submission (disabled button, spinner)
- [ ] Responsive layout (works on mobile)
- [ ] Accessible (label, aria attributes, keyboard submit with Enter)
- [ ] Matches existing app visual style (Tailwind CSS)
- [ ] No email/username field — password only
- [ ] In development mode (auth disabled): visiting `/login` redirects to `/`

### Component Structure

```tsx
// web/src/routes/login.tsx
// - App title/branding
// - PasswordInput (autoFocus)
// - SubmitButton ("Sign in")
// - ErrorMessage (conditionally shown, handles 401 and 429 differently)
```

### Files Changed

- `web/src/routes/login.tsx` — new file, login page route
- `web/src/routeTree.gen.ts` — auto-regenerated by TanStack Router

### Testing (E2E)

- Login page renders with password field and submit button
- Submitting correct password redirects to home
- Submitting wrong password shows error
- Enter key submits form
- Button shows loading state during submission
- In dev mode, `/login` redirects to `/`

---

## Task 2.2: Add Session Check to App Root and API Client

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 2.1

### Description

Add a session check using TanStack Router's `beforeLoad` hook that redirects unauthenticated users to `/login`. Add `credentials: "include"` to the API client for cross-origin cookie support.

### Acceptance Criteria

- [ ] `beforeLoad` hook on root route calls `GET /api/v1/auth/session`
- [ ] If `{ authenticated: false }`: redirect to `/login?returnTo=<current_path>`
- [ ] If `{ authenticated: true }`: render app normally
- [ ] TanStack Router's pending state shown while checking session (no flash-of-content)
- [ ] `/login` route itself does NOT trigger the session check (avoid redirect loop)
- [ ] Session check result cached via TanStack Query (staleTime: 5 min)
- [ ] If session check fails (network error): show retry option, not login redirect
- [ ] When `VITE_AUTH_ENABLED` is `false` (or unset in dev): skip session check entirely
- [ ] API client adds `credentials: "include"` when `VITE_API_URL` is set (cross-origin deployments)

### Implementation Notes

```tsx
// web/src/routes/__root.tsx — use beforeLoad for auth guard
export const Route = createRootRoute({
  beforeLoad: async ({ location }) => {
    if (location.pathname === '/login') return  // Skip for login page
    if (!isAuthEnabled()) return                 // Skip in dev mode

    const session = await checkSession()
    if (!session.authenticated) {
      throw redirect({
        to: '/login',
        search: { returnTo: location.pathname },
      })
    }
  },
  component: RootComponent,
})
```

```typescript
// web/src/lib/api/client.ts — cross-origin credentials
const fetchOptions: RequestInit = {
  // Include cookies in cross-origin requests when API is on a different host
  credentials: import.meta.env.VITE_API_URL ? "include" : "same-origin",
}
```

### Files Changed

- `web/src/routes/__root.tsx` — add `beforeLoad` session check
- `web/src/lib/api/auth.ts` — new file, auth API functions (`checkSession`, `login`, `logout`)
- `web/src/lib/api/client.ts` — add `credentials` option for cross-origin
- `web/src/lib/api/index.ts` — re-export auth functions

### Testing (E2E)

- Unauthenticated visit to `/` redirects to `/login`
- Unauthenticated visit to `/digests` redirects to `/login?returnTo=/digests`
- After login, redirect back to intended page
- Authenticated user sees app normally (no redirect, no flash)
- Login page is accessible without authentication
- Cross-origin: cookies included in requests when `VITE_API_URL` set

---

## Task 3.1: Backend Tests

**Priority**: P0
**Estimate**: 4 hours
**Dependencies**: Tasks 1.1–1.4

### Description

Write comprehensive backend tests for auth endpoints, middleware, rate limiter, and security properties.

### Acceptance Criteria

- [ ] `tests/api/test_auth_routes.py` — endpoint tests
- [ ] `tests/api/test_auth_middleware.py` — middleware tests
- [ ] `tests/api/test_rate_limiter.py` — rate limiter tests
- [ ] `tests/security/test_owner_auth.py` — security-specific tests

### Test Cases

**Auth endpoints (`test_auth_routes.py`):**
- Login with correct password → 200 + session cookie
- Login with wrong password → 401 + WARNING log with client IP
- Successful login → INFO log with client IP
- Login with empty password → 401 (or 422)
- Login when APP_SECRET_KEY not configured → 500
- Logout → cookie cleared
- Session check with valid cookie → `{ authenticated: true }`
- Session check without cookie → `{ authenticated: false }`
- Session check with expired JWT → `{ authenticated: false }`
- SameSite=None when cross-origin ALLOWED_ORIGINS configured
- SameSite=Lax when same-origin only

**Auth middleware (`test_auth_middleware.py`):**
- Protected endpoint with valid cookie → 200
- Protected endpoint with valid X-Admin-Key → 200
- Protected endpoint with neither → 401
- Protected endpoint with expired cookie → 401
- Exempted endpoint without auth → 200 (health, ready, system/config)
- Auth endpoints without auth → 200 (no redirect loop)
- Development mode: all endpoints accessible without auth
- Sliding window: response cookie has refreshed expiry when token > 1 day old
- Sliding window: response cookie NOT refreshed when token < 1 day old
- SSE endpoint: 401 returned before any streaming data sent

**Rate limiter (`test_rate_limiter.py`):**
- 5 failures → 6th attempt returns 429 with Retry-After header
- Different IPs tracked independently
- Entries expire after window (time-mocked)
- Memory cleanup works
- Lockout message includes human-readable retry time

**Security tests (`test_owner_auth.py`):**
- JWT with wrong signature rejected
- JWT with tampered payload rejected
- JWT signed with raw APP_SECRET_KEY (not HMAC-derived) rejected
- JWT signed with different key rejected
- Cookie flags verified (HttpOnly, SameSite, Path)
- Timing-safe comparison used (not just `==`)

### Files Changed

- `tests/api/test_auth_routes.py` — new file
- `tests/api/test_auth_middleware.py` — new file
- `tests/api/test_rate_limiter.py` — new file
- `tests/security/test_owner_auth.py` — new file

---

## Task 3.2: E2E Tests

**Priority**: P1
**Estimate**: 3 hours
**Dependencies**: Tasks 2.1–2.2, 3.1

### Description

Write Playwright E2E tests for the login flow and protected routes.

### Acceptance Criteria

- [ ] E2E test file: `web/tests/e2e/auth/login.spec.ts`
- [ ] Uses mock API routes (no real backend needed, consistent with existing E2E approach)
- [ ] Import custom `test` from `../fixtures` (not `@playwright/test`)

### Test Cases

- Visit `/` without session → redirected to `/login`
- Login page renders password field and submit button
- Submit correct password → redirected to home (no flash-of-content)
- Submit wrong password → error message shown
- Submit with Enter key → form submits
- After login, navigate to other pages without redirect
- Logout → redirected to `/login`
- Visit `/login` when already authenticated → redirected to `/`
- `returnTo` parameter preserved through login flow
- Rate limited (429) → shows "too many attempts" message

### Files Changed

- `web/tests/e2e/auth/login.spec.ts` — new file
- `web/tests/e2e/fixtures/mock-data.ts` — add auth mock responses if needed

---

## Task 3.3: Update API Security Spec

**Priority**: P2
**Estimate**: 1 hour
**Dependencies**: Tasks 1.1–2.2

### Description

Update the OpenSpec API security specification to reflect the new authentication model.

### Acceptance Criteria

- [ ] `openspec/specs/api-security/spec.md` updated with owner auth model
- [ ] Document coexistence of session cookie + X-Admin-Key
- [ ] Document exempted paths
- [ ] Document configuration (APP_SECRET_KEY)
- [ ] Document cross-origin cookie strategy (SameSite auto-detection)
- [ ] Document rate limiting behavior
- [ ] Document dev mode bypass
- [ ] Document login auditing (log levels and format)

### Files Changed

- `openspec/specs/api-security/spec.md` — update existing spec

---

## Summary

**Total Tasks**: 9
**Total Estimate**: 23 hours (~3 days)

**Critical Path**:
```
1.1 (Settings) → 1.2 (Endpoints) → 1.3 (Rate limiter) ─┐
                       │                                   ├→ 1.4 (Middleware) → 3.1 (Backend tests)
                       ↓                                   │
                  2.1 (Login page) → 2.2 (Session check) ─┘→ 3.2 (E2E tests)
                                                                      ↓
                                                                3.3 (Update spec)
```

**Parallelization**:
- After 1.2: Tasks 1.3, 1.4, and 2.1 can run in parallel
- After 1.4 + 2.2: Tasks 3.1 and 3.2 can run in parallel
- Task 3.3 can run anytime after the implementation tasks

**Risk Areas**:
- Task 1.4 (middleware) — touches every request; must not break existing endpoints or SSE streaming
- Task 2.2 (session check) — must not create redirect loops or break dev mode
- Task 1.2 (cross-origin SameSite) — must detect deployment topology correctly
