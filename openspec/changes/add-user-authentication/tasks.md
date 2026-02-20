# Implementation Tasks: Owner Authentication (Phase 1)

## Task 1.1: Add `APP_SECRET_KEY` to Settings and Profiles

**Priority**: P0 (Blocker)
**Estimate**: 1 hour
**Dependencies**: None

### Description

Add the `app_secret_key` field to the Settings model and wire it into the profile system.

### Acceptance Criteria

- [ ] `app_secret_key: str | None` field added to `Settings` in `src/config/settings.py`
- [ ] `app_secret_key: "${APP_SECRET_KEY:-}"` added to `profiles/base.yaml` under `settings`
- [ ] Startup validator logs warning if `APP_SECRET_KEY` not set in production (like `admin_api_key`)
- [ ] Startup validator logs warning if key is < 32 characters
- [ ] Existing `ADMIN_API_KEY` behavior unchanged
- [ ] Tests pass with `_env_file=None` (no pickup from `.env`)

### Files Changed

- `src/config/settings.py` — add field + startup validation
- `profiles/base.yaml` — add `app_secret_key` reference

### Testing

- Settings loads with `APP_SECRET_KEY` from env
- Settings loads without `APP_SECRET_KEY` (None, no crash)
- Warning logged when missing in production
- Warning logged when key < 32 chars

---

## Task 1.2: Create Auth Endpoints

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 1.1

### Description

Create `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/session` endpoints.

### Acceptance Criteria

- [ ] `POST /api/v1/auth/login` accepts `{ "password": "..." }`
- [ ] Password verified with `secrets.compare_digest()` against `APP_SECRET_KEY`
- [ ] On success: returns 200 with `Set-Cookie: session=<JWT>` (HttpOnly, Secure in production, SameSite=Lax, Max-Age=604800, Path=/)
- [ ] On failure: returns 401 `{ "error": "Invalid credentials" }`
- [ ] JWT payload: `{ "iss": "newsletter-aggregator", "iat": <unix>, "exp": <unix+7d> }`
- [ ] JWT signed with HS256 using `APP_SECRET_KEY`
- [ ] `POST /api/v1/auth/logout` clears the session cookie (Set-Cookie with Max-Age=0)
- [ ] `GET /api/v1/auth/session` returns `{ "authenticated": true/false }` based on valid cookie
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
- Login with wrong password returns 401
- Login when `APP_SECRET_KEY` not set returns 500
- Logout clears session cookie
- Session endpoint returns status based on cookie validity
- JWT expiry is 7 days from login
- Cookie flags correct (HttpOnly, SameSite=Lax, Path=/)
- Secure flag only set when not in development

---

## Task 1.3: Create Auth Middleware

**Priority**: P0 (Blocker)
**Estimate**: 3 hours
**Dependencies**: Task 1.2

### Description

Create FastAPI middleware that enforces authentication on all endpoints except explicitly exempted ones. Supports both session cookies (browser) and `X-Admin-Key` headers (programmatic).

### Acceptance Criteria

- [ ] Middleware checks for `session` cookie first, then `X-Admin-Key` header
- [ ] Valid JWT in cookie: request proceeds, cookie refreshed with new expiry (sliding window)
- [ ] Valid `X-Admin-Key` header: request proceeds (backward compat)
- [ ] Neither present in production: returns 401
- [ ] Exempted paths skip auth entirely: `/health`, `/ready`, `/api/v1/system/config`, `/api/v1/otel/v1/traces`, `/api/v1/auth/*`
- [ ] Development mode (`ENVIRONMENT=development`): all requests pass (unchanged behavior)
- [ ] Middleware registered in `src/api/app.py` (before route registration)
- [ ] Existing `verify_admin_key` dependency on settings/prompts/contents routes unchanged (defense in depth)
- [ ] `ENDPOINT_AUTH_MAP` in `dependencies.py` updated to reflect new auth model

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

### Sliding Window Logic

```python
# On each authenticated request with a valid cookie:
# 1. Decode JWT (verify signature + expiry)
# 2. Issue new JWT with refreshed exp = now + 7 days
# 3. Set updated cookie on response
# Result: session only expires after 7 days of inactivity
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
- Cookie is refreshed on each authenticated request (sliding window)
- Development mode bypasses all auth
- Invalid JWT signature returns 401
- Tampered JWT returns 401

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
- [ ] Loading state during submission (disabled button, spinner)
- [ ] Responsive layout (works on mobile)
- [ ] Accessible (label, aria attributes, keyboard submit with Enter)
- [ ] Matches existing app visual style (Tailwind CSS)
- [ ] No email/username field — password only

### Component Structure

```tsx
// web/src/routes/login.tsx
// - PasswordInput (autoFocus)
// - SubmitButton ("Sign in")
// - ErrorMessage (conditionally shown)
// - App branding/title
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

---

## Task 2.2: Add Session Check to App Root

**Priority**: P0 (Blocker)
**Estimate**: 2 hours
**Dependencies**: Task 2.1

### Description

Add a session check in `__root.tsx` that redirects unauthenticated users to `/login`. Use `GET /api/v1/auth/session` to check auth status.

### Acceptance Criteria

- [ ] On app mount, call `GET /api/v1/auth/session`
- [ ] If `{ authenticated: false }`: redirect to `/login?returnTo=<current_path>`
- [ ] If `{ authenticated: true }`: render app normally
- [ ] Show loading indicator while checking session
- [ ] `/login` route itself does NOT trigger the session check (avoid redirect loop)
- [ ] Session check cached (don't re-check on every navigation)
- [ ] If session check fails (network error): show retry option, not login redirect
- [ ] When `VITE_AUTH_ENABLED` is `false` (or unset in dev): skip session check entirely

### Implementation Notes

```tsx
// web/src/routes/__root.tsx
// Option A: TanStack Router beforeLoad on root route
// Option B: useEffect in RootComponent with redirect

// Use TanStack Query for session check (caching, retry):
// queryKey: ["auth", "session"]
// queryFn: () => apiClient.get("/auth/session")
// staleTime: 5 minutes (don't re-check constantly)
```

### Files Changed

- `web/src/routes/__root.tsx` — add session check logic
- `web/src/lib/api/auth.ts` — new file, auth API functions (`checkSession`, `login`, `logout`)

### Testing (E2E)

- Unauthenticated visit to `/` redirects to `/login`
- Unauthenticated visit to `/digests` redirects to `/login?returnTo=/digests`
- After login, redirect back to intended page
- Authenticated user sees app normally (no redirect)
- Login page is accessible without authentication

---

## Task 3.1: Backend Tests

**Priority**: P0
**Estimate**: 3 hours
**Dependencies**: Tasks 1.1–1.3

### Description

Write comprehensive backend tests for auth endpoints and middleware.

### Acceptance Criteria

- [ ] `tests/api/test_auth_routes.py` — endpoint tests
- [ ] `tests/api/test_auth_middleware.py` — middleware tests
- [ ] `tests/security/test_owner_auth.py` — security-specific tests

### Test Cases

**Auth endpoints (`test_auth_routes.py`):**
- Login with correct password → 200 + session cookie
- Login with wrong password → 401
- Login with empty password → 401 (or 422)
- Login when APP_SECRET_KEY not configured → 500
- Logout → cookie cleared
- Session check with valid cookie → `{ authenticated: true }`
- Session check without cookie → `{ authenticated: false }`
- Session check with expired JWT → `{ authenticated: false }`

**Auth middleware (`test_auth_middleware.py`):**
- Protected endpoint with valid cookie → 200
- Protected endpoint with valid X-Admin-Key → 200
- Protected endpoint with neither → 401
- Protected endpoint with expired cookie → 401
- Exempted endpoint without auth → 200 (health, ready, system/config)
- Auth endpoints without auth → 200 (no redirect loop)
- Development mode: all endpoints accessible without auth
- Sliding window: response cookie has refreshed expiry

**Security tests (`test_owner_auth.py`):**
- JWT with wrong signature rejected
- JWT with tampered payload rejected
- JWT signed with different key rejected
- Cookie flags verified (HttpOnly, SameSite, Path)
- Timing-safe comparison used (not just `==`)

### Files Changed

- `tests/api/test_auth_routes.py` — new file
- `tests/api/test_auth_middleware.py` — new file
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
- Submit correct password → redirected to home
- Submit wrong password → error message shown
- Submit with Enter key → form submits
- After login, navigate to other pages without redirect
- Logout → redirected to `/login`
- Visit `/login` when already authenticated → redirected to `/`
- `returnTo` parameter preserved through login flow

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
- [ ] Document dev mode bypass

### Files Changed

- `openspec/specs/api-security/spec.md` — update existing spec

---

## Summary

**Total Tasks**: 8
**Total Estimate**: 19 hours (~2.5 days)

**Critical Path**:
```
1.1 (Settings) → 1.2 (Endpoints) → 1.3 (Middleware) → 3.1 (Backend tests)
                       ↓
                  2.1 (Login page) → 2.2 (Session check) → 3.2 (E2E tests)
                                                                    ↓
                                                              3.3 (Update spec)
```

**Parallelization**:
- After 1.2: Tasks 1.3 and 2.1 can run in parallel (backend middleware + frontend login page)
- After 1.3 + 2.2: Tasks 3.1 and 3.2 can run in parallel (backend tests + E2E tests)
- Task 3.3 can run anytime after the implementation tasks

**Risk Areas**:
- Task 1.3 (middleware) — touches every request; must not break existing endpoints
- Task 2.2 (session check) — must not create redirect loops or break dev mode
