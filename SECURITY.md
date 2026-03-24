# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Use [GitHub Security Advisories](../../security/advisories/new) to report privately
3. Or email security concerns to the repository maintainers

## What to Report

- Authentication or authorization bypasses
- Cross-site scripting (XSS) or injection vulnerabilities
- Server-side request forgery (SSRF)
- Sensitive data exposure
- Denial of service vulnerabilities

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium/Low: Next release cycle

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |

## Security Measures

This project implements:

- **Authentication**: Single-owner session cookies and API key authentication
- **CORS**: Configurable allowed origins with production fail-safe
- **Security Headers**: HSTS, CSP (report-only), X-Frame-Options, and more
- **Secret Scanning**: Pre-commit hooks and CI scanning via gitleaks
- **Dependency Scanning**: Automated pip-audit and pnpm audit in CI
- **Input Validation**: File upload magic bytes verification, SSRF protection
- **Rate Limiting**: Login endpoint rate limiting

## Branch Protection (Recommended)

For production deployments, configure GitHub branch protection:

- Require pull request reviews (1+ reviewer)
- Require status checks: `lint`, `test`, `secret-scan`
- Require branches to be up to date before merging
- Disallow force-push to main
- Disallow direct commits to main

## Development Security

- Never commit secrets — gitleaks pre-commit hook prevents this
- Use `.secrets.yaml` (gitignored) for local credentials
- Use `profiles/*.yaml` with `${VAR}` interpolation for configuration
- Default docker-compose credentials are for local development only
