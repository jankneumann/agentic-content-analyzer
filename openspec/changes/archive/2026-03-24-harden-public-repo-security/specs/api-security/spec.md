# API Security: Public Repository Hardening

## ADDED Requirements

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
