# Security Review Report

## Run Context

- Change ID: `closeout-db-source-overrides-evidence`
- Commit SHA: 8c6af6839a6bbb35e0d402431ee56d2efea68c45
- Timestamp: 2026-09-22T03:23:20.135149+00:00
- Profile: `mixed`
- Confidence: `high`

## Gate Summary

- Decision: **PASS WITH WARNINGS**
- Change-scoped fail threshold: `high`
- New threshold findings: `0`

## Scanner Results

| Scanner | Status | Notes |
|---|---|---|
| OWASP dependency-check | degraded | Rootless container scan could not read all repository cache files. |
| ZAP baseline | pass | Direct rerun against the host-accessible API: 0 failures, 1 low-risk cache warning. |
| pip-audit | pass | No known vulnerabilities in the local Python environment. |
| pnpm audit | warn | 29 high and 6 moderate advisories; identical result on `main`, tracked in issue #530. |

## Severity Summary

- New change-scoped findings: `0`
- Critical: `0`
- High: `0`
- Medium: `0`
- Low: `1` ZAP warning (`Non-Storable Content` on authenticated root/robots responses)
- Info: `0`

## Gate Reasons

- ZAP and focused authentication/privacy tests found no threshold issue.
- Python dependencies have no known vulnerability.
- Frontend advisories predate this branch and reproduce on `main`; remediation
  is explicitly tracked in issue #530 rather than hidden or attributed to this
  source-override closeout.

## Top Findings

- Pre-existing frontend transitive advisories in `fast-uri`,
  `brace-expansion`, `@xmldom/xmldom`, and `js-yaml` (issue #530).
- ZAP cacheability warning on 401 responses; no failed passive rule.
