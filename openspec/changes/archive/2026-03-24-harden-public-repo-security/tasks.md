# Tasks: Harden Public Repo Security

## 1. Secret Scanning Infrastructure

### 1.1 Gitleaks Configuration
- [x] Create `.gitleaks.toml` with project-specific allowlist
  - Allow `test-key`, `test-admin-key` patterns in test fixtures
  - Allow `newsletter_password` in docker-compose (with warning comments)
  - Allow `sk-ant-` in documentation/examples only
  - Allow `.secrets.yaml.example` template keys
- [x] Test gitleaks against current repo: `gitleaks detect --source . --verbose`
- [x] Document any findings and remediation plan

### 1.2 Pre-commit Hook
- [x] Add gitleaks hook to `.pre-commit-config.yaml`
  - Hook: `gitleaks protect --staged`
  - Runs on all file types
- [x] Verify hook catches staged secrets in test commit
- [x] Update CLAUDE.md gotchas with gitleaks pre-commit notes

### 1.3 Git History Audit
- [x] Run full history scan: `gitleaks detect --source . --log-opts="--all"`
- [x] Document findings in audit report
- [x] If secrets found: rotate credentials, plan BFG cleanup
- [x] Verify clean history after remediation

## 2. CI Security Workflows

### 2.1 Secret Scanning Workflow
- [x] Create `.github/workflows/security.yml`
  - Trigger: push to main, pull_request
  - Job: `gitleaks/gitleaks-action@v2`
  - Upload SARIF results for GitHub Security tab
- [x] Test workflow on feature branch PR

### 2.2 Dependency Vulnerability Scanning
- [x] Add `pip-audit` to `pyproject.toml` dev dependencies
- [x] Add pip-audit CI step (Python dependencies)
  - `pip-audit --format json --output pip-audit-results.json`
  - Fail on high/critical severity
- [x] Add pnpm audit CI step (Node dependencies)
  - `cd web && pnpm audit --audit-level=high`
  - Allow known acceptable advisories via `.pnpm-audit-known.json`
- [x] Test both scanners locally first

### 2.3 CI Integration
- [x] Ensure security workflow runs in parallel with existing lint/test jobs
- [x] Add security scan status check to branch protection recommendations
- [x] Document CI security gates in SECURITY.md

## 3. Security Headers Middleware

### 3.1 Implement SecurityHeadersMiddleware
- [x] Create `src/api/middleware/security_headers.py`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 0` (disabled per MDN guidance)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - HSTS: production only (`Strict-Transport-Security: max-age=31536000; includeSubDomains`)
  - CSP: report-only mode initially
- [x] Register middleware in `src/api/app.py` (after CORS, before auth)
- [x] Verify headers don't break CORS preflight (OPTIONS requests)

### 3.2 Test Security Headers
- [x] Create `tests/api/test_security_headers.py`
  - Test all headers present on normal responses
  - Test HSTS absent in development, present in production
  - Test CSP is report-only (not enforcing)
  - Test headers present on error responses (4xx, 5xx)
  - Test OPTIONS preflight still works with headers
- [x] Run existing E2E tests to verify no regressions

## 4. Production Validation Improvements

### 4.1 Extend Settings Validation
- [x] Add weak-secret detection to `_validate_production_config()`
  - Warn if `APP_SECRET_KEY` in common defaults list
  - Warn if `ADMIN_API_KEY` < 32 characters
  - Warn if `DATABASE_URL` contains `newsletter_password`
- [x] Add common defaults list: `["changeme", "secret", "password", "admin", "test"]`

### 4.2 Test Extended Validation
- [x] Add tests to `tests/config/test_production_validation.py`
  - Test weak secret detection triggers warning
  - Test default DB password detection triggers warning
  - Test strong secrets pass validation
- [x] Verify existing production validation tests still pass

## 5. Repository Hygiene

### 5.1 Docker Compose Credential Documentation
- [x] Add warning comments to `docker-compose.yml` default passwords
  - `# WARNING: Development credentials only. Never use in production.`
- [x] Add same warnings to `docker-compose.opik.yml`
- [x] Add same warnings to `docker-compose.supabase.yml`
- [x] Add same warnings to `docker-compose.langfuse.yml`

### 5.2 SECURITY.md
- [x] Create `SECURITY.md` at repo root
  - Responsible disclosure policy
  - Security contact (email or GitHub Security Advisories)
  - Supported versions table
  - Scope of security reports
  - Expected response timeline
  - Credit/acknowledgment policy
- [x] Link SECURITY.md from README (if exists) or CLAUDE.md

### 5.3 Branch Protection Documentation
- [x] Document recommended GitHub branch protection rules in SECURITY.md
  - Require PR reviews (1 minimum)
  - Require status checks: lint, test, security-scan
  - Require up-to-date branches
  - Disallow force-push to main
  - Disallow branch deletion for main
- [x] Note: Rules must be applied manually via GitHub Settings

## 6. Documentation Updates

### 6.1 CLAUDE.md Updates
- [x] Add gitleaks pre-commit gotcha
- [x] Add pip-audit / pnpm audit commands to testing section
- [x] Add security headers middleware to architecture notes
- [x] Document `.gitleaks.toml` allowlist maintenance

### 6.2 Spec Deltas
- [x] Update `api-security` spec with security headers requirements
- [x] Add secret scanning requirements
- [x] Add dependency scanning requirements

## Dependencies

```
1.1 ─┬─► 1.2 (gitleaks config needed before hook)
     └─► 1.3 (config needed for history audit)

2.1 ──── (independent, needs gitleaks config for allowlist reference)
2.2 ──── (independent)
2.3 ────► 2.1 + 2.2 (integrates both scanning types)

3.1 ────► 3.2 (middleware needed before tests)

4.1 ────► 4.2 (validation needed before tests)

5.1 ──── (independent)
5.2 ──── (independent)
5.3 ──── (independent)

6.1 ────► all (documentation reflects final state)
6.2 ────► all (specs reflect final state)
```
