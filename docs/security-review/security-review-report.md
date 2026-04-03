# Security Review Report

## Run Context

- Change ID: `agentic-analysis-agent`
- Commit SHA: 266b3252eafba7d3711de07ae671b9625dbc6b63
- Timestamp: 2026-04-02T16:43:00.235625+00:00
- Profile: `mixed`
- Confidence: `high`

## Gate Summary

- Decision: **PASS**
- Fail threshold: `high`
- Triggered findings: `0`

## Scanner Results

| Scanner | Status | Notes |
|---|---|---|
| dependency-check | error | native dependency-check failed (exit 14); docker fallback failed (exit 13) |
| zap | error | zap baseline scan failed via docker (exit 3) |

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
