# Security Review: Public Repository / Public Deployment Readiness

Date: 2026-03-22
Scope: `src/` API, auth, URL ingestion, storage access, and operational defaults.

## Round 2 update (2026-03-22)

The following hardening items were implemented after the initial review:

- Restricted unauthenticated development-mode bypass to **local loopback/test clients only**.
- Removed raw `X-Forwarded-For` trust in shared endpoint rate limiting path.
- Added per-IP rate limiting on `/api/v1/otel/v1/traces`.

## Executive Summary

The codebase has a number of solid baseline protections (JWT auth cookie, timing-safe key checks, upload signature checks, path traversal guards, and SSRF filtering), but there are several **pre-public hardening items** you should address before exposing this project broadly:

1. **Risk of accidental unauthenticated deployment if `ENVIRONMENT` remains `development` and no keys are set.**
2. **Potential SSRF bypass via DNS rebinding race (already acknowledged in code comments).**
3. **Public endpoints use in-memory/per-process rate limits and trust client-controlled forwarding headers.**
4. **Unauthenticated OTLP proxy endpoint can be used for traffic/ingestion abuse.**

---

## Findings

## 1) Authentication bypass in development mode can expose all protected endpoints

**Severity:** High (configuration-dependent)

### Why it matters
If the service is deployed publicly with the default `environment=development` and without auth keys configured, authentication middleware allows all requests.

### Evidence
- Default environment is development. (`environment: ... = "development"`).
- Middleware explicitly bypasses auth in development when keys are not configured.

### Affected code
- `src/config/settings.py`
- `src/api/middleware/auth.py`

### Recommendation
- Fail fast on startup when running outside localhost unless one of:
  - `ENVIRONMENT=production|staging` **and** auth is configured, or
  - explicit `ALLOW_INSECURE_DEV_AUTH_BYPASS=true` is set.
- For public deployments, require **both** `APP_SECRET_KEY` and `ADMIN_API_KEY`.

---

## 2) SSRF validation has DNS rebinding exposure

**Severity:** High

### Why it matters
The URL validator resolves hostnames and checks IP classes, but the fetch uses normal DNS resolution later. An attacker can exploit DNS rebinding between validation and connection.

### Evidence
- The validator itself notes this limitation in a code comment.
- URL extraction depends on this validator for SSRF prevention.

### Affected code
- `src/utils/security.py`
- `src/services/url_extractor.py`

### Recommendation
- Implement fetch-by-resolved-IP strategy with TLS SNI/Host header controls.
- Re-validate every redirect target and connection target at socket-connect time.
- Optionally maintain explicit allowlist for domains for `save-url` workflows.

---

## 3) Rate limiting can be bypassed/spoofed in real deployments

**Severity:** Medium

### Why it matters
Public routes use an in-memory limiter and derive client IP from `X-Forwarded-For` directly. This is vulnerable when requests can set/spoof that header or when running multiple app instances.

### Evidence
- Shared routes trust first `X-Forwarded-For` value.
- Limiter is in-process memory only.

### Affected code
- `src/api/shared_routes.py`
- `src/api/rate_limiter_base.py`
- `src/api/share_rate_limiter.py`

### Recommendation
- Trust proxy headers only from known reverse proxies.
- Move rate limiting to a shared backend (Redis or database-backed).
- Add token-based throttles (not only IP-based) on shared-link endpoints.

---

## 4) OTLP proxy endpoint is unauthenticated and not rate limited

**Severity:** Medium

### Why it matters
`/api/v1/otel/v1/traces` is exempt from auth and forwards to configured collector with backend headers. This can be abused for telemetry spam, quota exhaustion, and downstream load.

### Evidence
- Exempt from auth middleware.
- Endpoint has content-type and payload-size checks, but no client auth/rate limiting.

### Affected code
- `src/api/middleware/auth.py`
- `src/api/otel_proxy_routes.py`

### Recommendation
- Add dedicated rate limit for OTLP proxy route.
- Optionally require a lightweight public ingestion token or strict CORS/origin validation.
- Consider disabling endpoint unless browser telemetry is explicitly needed.

---

## 5) Session model has no server-side revocation and long-lived cookies

**Severity:** Low/Medium

### Why it matters
JWTs are valid for 7 days, and logout deletes local cookie only. Secret rotation revokes all tokens, but per-session revocation is not available.

### Evidence
- JWT expiry is 7 days.
- No `jti`/denylist store.

### Affected code
- `src/api/auth_routes.py`

### Recommendation
- Shorten expiry for public deployment or add refresh tokens.
- Add optional `jti` + denylist for revocation on suspicious sessions.

---

## Existing strengths

- Timing-safe comparisons for credentials.
- Secure cookie flags in non-development environments.
- Upload validation with extension↔MIME and magic-byte checks.
- Local storage path traversal defense using resolved path boundary checks.
- Public share markdown rendering disables raw HTML (`html=False`).

---

## Public-readiness checklist

- [ ] Deploy with `ENVIRONMENT=production`.
- [ ] Set strong `APP_SECRET_KEY` (>=32 chars) and `ADMIN_API_KEY`.
- [ ] Set explicit `ALLOWED_ORIGINS` (no wildcard in production).
- [ ] Replace in-memory rate limiting with distributed limiter.
- [ ] Harden SSRF handling against DNS rebinding.
- [ ] Add throttling/authn for OTLP proxy or disable endpoint.
- [ ] Run secret scanning in CI (e.g., `gitleaks`/`detect-secrets`) and dependency CVE scanning.
