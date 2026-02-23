# Security Review Report

## Run Context

- Change ID: `content-sharing`
- Commit SHA: bbeffd89bade532ffef044e1fc7c8db0bfbbb466
- Timestamp: 2026-02-22T23:20:27.562372+00:00
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
