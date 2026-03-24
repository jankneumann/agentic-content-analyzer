# Design: Harden Public Repo Security

## Architecture Overview

This change is primarily additive — new CI workflows, new middleware, new documentation. It touches four distinct zones with minimal coupling between them.

```
┌─────────────────────────────────────────────────────────┐
│                    Repository Layer                       │
│  .github/workflows/  │  .pre-commit-config  │  SECURITY.md│
│  Branch protection    │  detect-secrets/gitleaks          │
└─────────────────┬─────┴──────────────┬───────────────────┘
                  │                    │
┌─────────────────▼────────────────────▼───────────────────┐
│                    Application Layer                      │
│  SecurityHeadersMiddleware  │  Production validation      │
│  src/api/middleware/        │  src/config/settings.py     │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                    Documentation Layer                    │
│  SECURITY.md  │  docker-compose warnings  │  SETUP.md   │
└─────────────────────────────────────────────────────────┘
```

## Decision: Secret Scanning Tool

### Options Considered

| Tool | Pros | Cons |
|------|------|------|
| **gitleaks** | Fast, single binary, GitHub Action available, scans history | Go binary (not Python) |
| **detect-secrets** | Python-native, Yelp-maintained, pre-commit plugin | Slower on full history, requires baseline file |
| **trufflehog** | Deep scanning, verified secrets | Heavy, cloud-focused |

### Decision: gitleaks

- Pre-commit hook: `gitleaks protect --staged` (fast, only staged files)
- CI workflow: `gitleaks detect` (full history scan on PRs)
- GitHub Action: `gitleaks/gitleaks-action@v2` (native integration)
- Allowlist: `.gitleaks.toml` for test fixtures and example files

**Why**: Single tool for both pre-commit and CI. Fast enough for pre-commit (<1s on staged files). Full history scan in CI catches anything that slipped past hooks.

## Decision: Dependency Scanning

### Backend (Python)

Use `pip-audit` — lightweight, pip-native, uses OSV database:
```yaml
# CI step
- run: pip-audit --require-hashes --desc on --format json
```

### Frontend (Node)

Use built-in `npm audit`:
```yaml
# CI step
- run: cd web && pnpm audit --audit-level=high
```

### Decision: No OWASP Dependency-Check

OWASP Dependency-Check is comprehensive but heavy (JVM-based, slow CI). `pip-audit` + `npm audit` cover 95% of CVE detection for our stack with faster execution.

## Decision: Security Headers

Add a dedicated `SecurityHeadersMiddleware` to `src/api/middleware/security_headers.py`:

```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",  # Disabled per MDN recommendation (CSP preferred)
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# HSTS only in production (breaks local dev over HTTP)
if environment == "production":
    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

# CSP in report-only mode initially
headers["Content-Security-Policy-Report-Only"] = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https:; "
    "font-src 'self'; "
    "frame-ancestors 'none'"
)
```

### Why X-XSS-Protection: 0?

Modern browsers have deprecated the XSS auditor. MDN recommends disabling it and relying on CSP instead. Setting it to `1; mode=block` can actually introduce vulnerabilities in older browsers.

### Why CSP Report-Only First?

Content-Security-Policy can break legitimate functionality (inline scripts, third-party resources). Starting in report-only mode lets us identify violations without blocking users, then promote to enforcing after verification.

## Decision: Branch Protection

Document recommended settings in SECURITY.md (can't enforce programmatically without admin access):

- Require PR reviews before merge (1 reviewer minimum)
- Require status checks: lint, test, security-scan
- Require branches be up to date before merge
- Disallow force-push to main
- Disallow direct commits to main

## Decision: Production Validation Improvements

Extend existing `_validate_production_config()` in `src/config/settings.py`:

**Current** (from prior hardening):
- Fails if both `APP_SECRET_KEY` and `ADMIN_API_KEY` missing
- Fails if `APP_SECRET_KEY` < 32 chars
- Warns on localhost-only CORS

**New additions**:
- Warn if `APP_SECRET_KEY` equals common defaults (e.g., "changeme", "secret")
- Warn if `ADMIN_API_KEY` < 32 chars (not just `APP_SECRET_KEY`)
- Warn if database URL contains default password (`newsletter_password`)

## Decision: Git History Audit

Run `gitleaks detect --source . --verbose` against full history before going public. If secrets found:

1. Rotate all affected credentials immediately
2. Use BFG Repo-Cleaner to remove from history
3. Force-push cleaned history (requires coordination with all contributors)
4. Re-run gitleaks to verify clean

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `.gitleaks.toml` | Gitleaks configuration and allowlist |
| `.github/workflows/security.yml` | Security scanning CI workflow |
| `src/api/middleware/security_headers.py` | Security response headers |
| `SECURITY.md` | Responsible disclosure policy |

### Modified Files
| File | Change |
|------|--------|
| `.pre-commit-config.yaml` | Add gitleaks hook |
| `src/api/app.py` | Register SecurityHeadersMiddleware |
| `src/config/settings.py` | Extended production validation |
| `docker-compose.yml` | Add credential warning comments |
| `docker-compose.opik.yml` | Add credential warning comments |
| `docker-compose.supabase.yml` | Add credential warning comments |
| `docker-compose.langfuse.yml` | Add credential warning comments |
| `pyproject.toml` | Add pip-audit dev dependency |
| `CLAUDE.md` | Add security scanning gotchas |

### Test Files
| File | Purpose |
|------|---------|
| `tests/api/test_security_headers.py` | Verify all headers present in responses |
| `tests/config/test_production_validation.py` | Extended validation checks |
