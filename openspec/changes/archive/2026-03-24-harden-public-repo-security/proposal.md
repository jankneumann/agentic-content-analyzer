# Proposal: Harden Public Repo Security

## Summary

Prepare the repository for public GitHub visibility by adding automated security gates, repository hygiene improvements, and security documentation. The application-level security (auth, SSRF, rate limiting) was already hardened in prior PRs; this proposal addresses the remaining supply-chain, CI/CD, and repository-level concerns.

## Problem

The repository is currently private. Before making it public, we must ensure:

1. **No secrets in git history** — tracked credential files, hardcoded passwords, or API keys
2. **Automated security scanning** — secret detection, dependency vulnerability checks, and SAST in CI
3. **Security headers** — standard browser protection headers missing from API responses
4. **Responsible disclosure** — no SECURITY.md or vulnerability reporting process
5. **Branch protection** — no rules preventing direct pushes to main or force-push
6. **Dependency audit** — no automated CVE scanning for Python or Node dependencies

## Scope

### In Scope

- Pre-commit secret scanning (detect-secrets or gitleaks)
- CI secret scanning workflow
- CI dependency vulnerability scanning (pip-audit + npm audit)
- Security response headers middleware (HSTS, X-Content-Type-Options, X-Frame-Options, CSP)
- SECURITY.md with responsible disclosure policy
- Git history audit for leaked secrets
- Docker compose credential documentation improvements
- GitHub branch protection configuration
- Production startup validation improvements

### Out of Scope

- Multi-user authentication (separate feature)
- WAF or DDoS protection (infrastructure-level, not app-level)
- DAST scanning (covered by existing `/security-review` skill)
- Penetration testing
- SOC2/compliance certification

## Success Criteria

1. `gitleaks detect` reports zero findings on full git history
2. CI pipeline includes secret scanning, dependency audit, and SAST gates
3. All API responses include security headers (HSTS, nosniff, frame-deny)
4. SECURITY.md exists with responsible disclosure instructions
5. Branch protection rules documented and ready to apply
6. Pre-commit hooks catch secrets before they reach git

## Prior Art

- Sentinel bot PRs fixed auth bypass, XSS, rate limiting (merged to main)
- `tests/security/` has error sanitization, SSRF, auth, and digest auth tests
- `scripts/check-profile-secrets.sh` scans profile YAML for hardcoded keys
- `.pre-commit-config.yaml` has private key detection via `detect-private-key`

## Risks

| Risk | Mitigation |
|------|-----------|
| Git history rewrite needed for leaked secrets | Audit first; if secrets found, use BFG Repo-Cleaner before going public |
| False positives in secret scanning | Configure allowlist for test fixtures and example files |
| Security headers break CORS/embedding | Test headers against existing E2E suite; CSP in report-only mode first |
| CI overhead from scanning | Run security scans only on PR + main push, not on every commit |

## Overlap with Other Proposals

- **add-deployment-pipeline**: Minor overlap on `.github/workflows/` — security scanning workflows are additive, not conflicting. If deployment pipeline lands first, security jobs integrate into the existing CI matrix.
