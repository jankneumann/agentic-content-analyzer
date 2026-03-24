# api-security Specification

## Purpose
Define the authentication, authorization, and input validation security model for the API. Covers owner authentication (session cookies + API keys), rate limiting, CORS policy, file upload validation, and production security configuration.
## Requirements
### Requirement: Authenticated access for protected APIs
The system SHALL require authenticated access for non-public API endpoints in production environments. Authentication is enforced via middleware that checks both session cookies (browser) and `X-Admin-Key` headers (CLI/extensions).

#### Scenario: Production request without credentials
- **WHEN** a client calls a protected endpoint without valid credentials in production
- **THEN** the API returns a 401 Unauthorized response

#### Scenario: Production request with valid session cookie
- **WHEN** a client calls a protected endpoint with a valid JWT session cookie in production
- **THEN** the API returns the requested resource

#### Scenario: Production request with valid X-Admin-Key
- **WHEN** a client calls a protected endpoint with a valid `X-Admin-Key` header in production
- **THEN** the API returns the requested resource

#### Scenario: Development request without credentials
- **WHEN** a client calls a protected endpoint without credentials in development mode
- **THEN** the API allows access without authentication (dev-mode bypass)

#### Scenario: Development request with invalid credentials
- **WHEN** a client provides an invalid API key in development mode
- **THEN** the API returns a 403 Forbidden response (explicit keys are always validated)

### Requirement: Production security configuration validation
The system SHALL validate security-critical configuration at startup in production environments.

#### Scenario: Production startup without ADMIN_API_KEY
- **WHEN** the application starts with `ENVIRONMENT=production` and `ADMIN_API_KEY` is not set
- **THEN** the system logs a security warning identifying the missing configuration

#### Scenario: Production startup without APP_SECRET_KEY
- **WHEN** the application starts with `ENVIRONMENT=production` and `APP_SECRET_KEY` is not set
- **THEN** the system logs a security warning identifying the missing configuration

#### Scenario: Production startup with weak APP_SECRET_KEY
- **WHEN** the application starts with `ENVIRONMENT=production` and `APP_SECRET_KEY` is less than 32 characters
- **THEN** the system logs a security warning about insufficient key length

#### Scenario: Production startup with dev-default CORS origins
- **WHEN** the application starts with `ENVIRONMENT=production` and `ALLOWED_ORIGINS` contains only localhost origins
- **THEN** the system logs a security warning about permissive CORS defaults

#### Scenario: Production startup with valid security configuration
- **WHEN** the application starts with `ENVIRONMENT=production`, both `ADMIN_API_KEY` and `APP_SECRET_KEY` are set, and `ALLOWED_ORIGINS` contains explicit non-localhost origins
- **THEN** the system starts without security warnings

### Requirement: Environment-configured CORS policy
The system SHALL load allowed CORS origins from configuration and apply restrictive defaults in production.

#### Scenario: Production request without explicit CORS configuration
- **WHEN** a browser client makes a cross-origin request in production and no explicit `ALLOWED_ORIGINS` is configured
- **THEN** the API response does NOT include the `Access-Control-Allow-Origin` header (default deny)

#### Scenario: Production request from explicitly allowed origin
- **WHEN** a browser client makes a request from an origin in the configured `ALLOWED_ORIGINS` list in production
- **THEN** the API response includes `Access-Control-Allow-Origin` matching the request origin

#### Scenario: Development request from local origin
- **WHEN** a browser client makes a request from `http://localhost:5173` in development mode
- **THEN** the API response includes `Access-Control-Allow-Origin: http://localhost:5173`

#### Scenario: CORS preflight from allowed origin
- **WHEN** a browser sends an OPTIONS preflight request from an origin in the configured allowlist
- **THEN** the API responds with appropriate `Access-Control-Allow-*` headers and 200 status

### Requirement: Owner authentication via session cookie
The system SHALL support password-based authentication for browser/mobile access using HttpOnly session cookies with JWT tokens.

#### Scenario: Login with correct password
- **WHEN** a client sends `POST /api/v1/auth/login` with the correct `APP_SECRET_KEY` password
- **THEN** the API returns 200 with `Set-Cookie: session=<JWT>` (HttpOnly, Secure in production, SameSite per configuration, Max-Age=604800, Path=/)

#### Scenario: Login with incorrect password
- **WHEN** a client sends `POST /api/v1/auth/login` with an incorrect password
- **THEN** the API returns 401 and logs a WARNING with the client IP address

#### Scenario: Logout
- **WHEN** a client sends `POST /api/v1/auth/logout`
- **THEN** the API clears the session cookie (Set-Cookie with Max-Age=0)

#### Scenario: Session check with valid cookie
- **WHEN** a client sends `GET /api/v1/auth/session` with a valid session cookie
- **THEN** the API returns `{ "authenticated": true }`

#### Scenario: Session check without cookie
- **WHEN** a client sends `GET /api/v1/auth/session` without a session cookie
- **THEN** the API returns `{ "authenticated": false }` (no 401 — safe to call without auth)

#### Scenario: JWT signing key derivation
- **WHEN** the system creates or verifies a JWT
- **THEN** the signing key is HMAC-derived from `APP_SECRET_KEY` via `hmac.new(key, b"jwt-signing-key", "sha256")` — the raw password is never used as a signing key

### Requirement: Dual authentication paths (session cookie + API key)
The system SHALL support both session cookies (browser) and `X-Admin-Key` headers (CLI/extensions) for authentication, with middleware enforcing auth on all non-exempt endpoints.

#### Scenario: Request with valid session cookie
- **WHEN** a client sends a request with a valid JWT session cookie
- **THEN** the middleware allows the request to proceed

#### Scenario: Request with valid X-Admin-Key header
- **WHEN** a client sends a request with a valid `X-Admin-Key` header (no cookie)
- **THEN** the middleware allows the request to proceed (backward compatibility)

#### Scenario: Request with neither credential in production
- **WHEN** a client sends a request without a session cookie or `X-Admin-Key` header in production
- **THEN** the middleware returns 401 Unauthorized (JSON format matching error handler)

#### Scenario: Sliding window token refresh
- **WHEN** a request has a valid session cookie whose `iat` claim is older than 1 day
- **THEN** the response includes an updated `Set-Cookie` with a refreshed JWT (new `iat` and `exp`)

#### Scenario: Token refresh skipped for fresh tokens
- **WHEN** a request has a valid session cookie whose `iat` claim is less than 1 day old
- **THEN** the response does NOT include a `Set-Cookie` header (avoids unnecessary cookie writes)

### Requirement: Auth-exempt endpoint allowlist
The system SHALL maintain a list of endpoints that are accessible without authentication for system health, telemetry, and the auth flow itself.

#### Scenario: System endpoint listed as exempt
- **WHEN** a client calls a system endpoint in the exempt list (`/health`, `/ready`, `/api/v1/system/config`, `/api/v1/otel/v1/traces`)
- **THEN** the API returns the response without requiring authentication

#### Scenario: Auth endpoint accessible without auth
- **WHEN** a client calls any `/api/v1/auth/*` endpoint (login, logout, session)
- **THEN** the API processes the request without requiring prior authentication (no redirect loop)

#### Scenario: Protected endpoint without credentials in production
- **WHEN** a client calls any non-exempt endpoint without valid credentials in production
- **THEN** the API returns a 401 Unauthorized response

#### Scenario: OpenAPI docs behind auth
- **WHEN** a client calls `/docs`, `/redoc`, or `/openapi.json` without authentication in production
- **THEN** the API returns 401 (API schema is intentionally protected)

### Requirement: Login rate limiting
The system SHALL rate-limit login attempts per client IP to mitigate brute-force attacks.

#### Scenario: Rate limit triggered
- **WHEN** a client IP has 5 failed login attempts within a 15-minute window
- **THEN** subsequent login attempts from that IP return 429 with a `Retry-After` header and human-readable message

#### Scenario: Different IPs tracked independently
- **WHEN** two different client IPs make login attempts
- **THEN** rate limiting is applied independently per IP (one IP's failures don't affect another)

#### Scenario: Rate limit window expiry
- **WHEN** a client IP's oldest failed attempt is older than 15 minutes
- **THEN** expired entries are pruned and the IP may attempt login again

#### Scenario: Successful login does not reset counter
- **WHEN** a client IP successfully logs in after previous failures
- **THEN** the failure counter is NOT reset (prevents timing attacks)

### Requirement: Cross-origin cookie support
The system SHALL support cross-origin cookie delivery for split deployments (e.g., Railway frontend and backend on different domains).

#### Scenario: Same-origin deployment (default)
- **WHEN** `AUTH_COOKIE_CROSS_ORIGIN` is `false` (default)
- **THEN** session cookies use `SameSite=Lax`

#### Scenario: Cross-origin deployment
- **WHEN** `AUTH_COOKIE_CROSS_ORIGIN` is `true`
- **THEN** session cookies use `SameSite=None` (requires `Secure=true`)

### Requirement: File upload signature validation
The system SHALL validate document uploads by checking file signatures (magic bytes) against the declared file extension.

#### Scenario: Upload with matching signature and extension
- **WHEN** a client uploads a file whose magic bytes match the declared extension (e.g., a `.pdf` file starting with `%PDF`)
- **THEN** the API accepts the upload for processing

#### Scenario: Upload with mismatched signature and extension
- **WHEN** a client uploads a file whose magic bytes do NOT match the declared extension (e.g., an executable renamed to `.pdf`)
- **THEN** the API rejects the upload with a 415 Unsupported Media Type response indicating signature mismatch

#### Scenario: Upload with unknown signature
- **WHEN** a client uploads a file with an extension that has no defined magic bytes mapping (e.g., `.txt`, `.md`)
- **THEN** the API skips signature validation and proceeds with extension-based format checking

### Requirement: Upload MIME type cross-check
The system SHALL validate that the client-provided MIME type is consistent with the declared file extension.

#### Scenario: Upload with consistent MIME type and extension
- **WHEN** a client uploads a file with MIME type `application/pdf` and extension `.pdf`
- **THEN** the API accepts the upload for processing

#### Scenario: Upload with contradictory MIME type and extension
- **WHEN** a client uploads a file with MIME type `image/png` but extension `.pdf`
- **THEN** the API rejects the upload with a 415 Unsupported Media Type response indicating type mismatch

#### Scenario: Upload with generic MIME type fallback
- **WHEN** a client uploads a file with MIME type `application/octet-stream` (browser/tool generic fallback)
- **THEN** the API skips MIME cross-check and proceeds with extension-based and signature-based validation only

### Requirement: Safe document upload size enforcement (existing)
The system SHALL validate document uploads with early size checks before full buffering.

#### Scenario: Upload exceeds configured size
- **WHEN** a client uploads a document larger than the configured limit
- **THEN** the API rejects the upload with a 413 Payload Too Large response without fully buffering the file

### Requirement: Sanitized error responses (existing)
The system SHALL avoid returning internal exception details in API error responses.

#### Scenario: Parser failure during upload
- **WHEN** a parsing exception occurs during upload processing
- **THEN** the API returns a generic error message without internal stack details or exception messages

### Requirement: Standard Security Response Headers

The API MUST include browser protection headers on all responses, including error responses: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 0`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy: camera=(), microphone=(), geolocation=()`.

#### Scenario: Security headers on successful API response

- **WHEN** a client sends a GET request to any API endpoint
- **THEN** the response MUST include `X-Content-Type-Options: nosniff`
- **AND** the response MUST include `X-Frame-Options: DENY`
- **AND** the response MUST include `X-XSS-Protection: 0`
- **AND** the response MUST include `Referrer-Policy: strict-origin-when-cross-origin`
- **AND** the response MUST include `Permissions-Policy: camera=(), microphone=(), geolocation=()`

#### Scenario: Security headers on error response

- **WHEN** a client sends a request that results in a 404 or 500 error
- **THEN** the response MUST include all standard security headers

### Requirement: HSTS Header in Production Only

When `ENVIRONMENT=production`, the API MUST include `Strict-Transport-Security: max-age=31536000; includeSubDomains`. In non-production environments, HSTS MUST NOT be present.

#### Scenario: HSTS present in production

- **GIVEN** `ENVIRONMENT=production`
- **WHEN** a client sends any request
- **THEN** the response MUST include `Strict-Transport-Security: max-age=31536000; includeSubDomains`

#### Scenario: HSTS absent in development

- **GIVEN** `ENVIRONMENT=development`
- **WHEN** a client sends any request
- **THEN** the response MUST NOT include `Strict-Transport-Security`

### Requirement: Content Security Policy Report-Only

The API MUST include a `Content-Security-Policy-Report-Only` header restricting `default-src` to `'self'` and disallowing `frame-ancestors`.

#### Scenario: CSP report-only header present

- **WHEN** a client sends any request
- **THEN** the response SHOULD include `Content-Security-Policy-Report-Only`
- **AND** the policy MUST include `default-src 'self'`
- **AND** the policy MUST include `frame-ancestors 'none'`

### Requirement: Security Headers Preserve CORS Preflight

SecurityHeadersMiddleware MUST NOT interfere with CORS preflight (OPTIONS) requests. CORSMiddleware's `Access-Control-Allow-*` headers MUST still appear on preflight responses.

#### Scenario: CORS preflight with security headers middleware active

- **GIVEN** both CORSMiddleware and SecurityHeadersMiddleware are registered
- **WHEN** a client sends an OPTIONS preflight request with an `Origin` header
- **THEN** the response MUST include `Access-Control-Allow-Origin`
- **AND** the response MUST include standard security headers

### Requirement: Pre-commit Secret Detection

The repository MUST include a pre-commit hook that prevents committing files containing secrets such as API keys or passwords.

#### Scenario: Secret blocked by pre-commit hook

- **WHEN** a developer stages a file containing a hardcoded API key pattern (e.g., `sk-ant-api03-...`)
- **AND** runs `git commit`
- **THEN** the pre-commit hook MUST block the commit with a secret detection warning

#### Scenario: Allowlisted test fixture passes

- **WHEN** a test fixture file containing `test-admin-key` is staged
- **AND** the pattern is in the scanning tool's allowlist
- **THEN** the pre-commit hook MUST NOT block the commit

### Requirement: CI Secret Scanning Workflow

The CI pipeline MUST include a job that scans the full repository and git history for secrets on every PR and push to main.

#### Scenario: CI detects secret in PR branch

- **WHEN** a PR branch contains a file with a hardcoded API key
- **AND** the CI security workflow runs
- **THEN** the workflow MUST fail with a finding identifying the secret location

### Requirement: CI Dependency Vulnerability Scanning

The CI pipeline MUST check Python and Node.js dependencies for known CVEs, failing on HIGH or CRITICAL severity.

#### Scenario: High-severity Python CVE detected

- **GIVEN** a Python dependency in `pyproject.toml` has a known HIGH severity CVE
- **WHEN** the dependency audit CI step runs
- **THEN** the step MUST fail with CVE details

#### Scenario: Medium-severity CVE passes with warning

- **GIVEN** a dependency has a MEDIUM severity CVE
- **WHEN** the dependency audit CI step runs
- **THEN** the step SHOULD report the CVE but MUST NOT fail the pipeline

### Requirement: Weak Secret Detection at Startup

Production startup validation MUST warn when `APP_SECRET_KEY` or `ADMIN_API_KEY` matches a common default value such as "changeme", "secret", or "password".

#### Scenario: Default APP_SECRET_KEY triggers warning

- **GIVEN** `ENVIRONMENT=production` and `APP_SECRET_KEY=changeme`
- **WHEN** the application starts
- **THEN** a WARNING log MUST be emitted indicating a weak secret is configured

### Requirement: Default Database Credential Detection

Production startup validation MUST warn when `DATABASE_URL` contains a known default password such as `newsletter_password`.

#### Scenario: Default database password triggers warning

- **GIVEN** `ENVIRONMENT=production` and `DATABASE_URL` contains `newsletter_password`
- **WHEN** the application starts
- **THEN** a WARNING log MUST be emitted indicating default database credentials are in use
