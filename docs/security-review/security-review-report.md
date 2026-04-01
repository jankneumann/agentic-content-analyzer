# Security Review Report

## Run Context

- Commit SHA: 349c0128a645ddd3d304a7711b779d2e46b0157f
- Timestamp: 2026-03-31T23:24:15.511972+00:00
- Profile: `mixed`
- Confidence: `high`

## Gate Summary

- Decision: **PASS**
- Fail threshold: `high`
- Triggered findings: `0`

## Scanner Results

| Scanner | Status | Notes |
|---|---|---|
| dependency-check | error | native dependency-check failed (exit 13); docker fallback failed (exit 13) |
| zap | unavailable | DAST profile requires --zap-target for ZAP execution |

## Severity Summary

- Total findings: `0`
- Critical: `0`
- High: `0`
- Medium: `0`
- Low: `0`
- Info: `0`

## Gate Reasons

- Degraded execution allowed by policy; no threshold findings detected

## Top Findings

- No findings
