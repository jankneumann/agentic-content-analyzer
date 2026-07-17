# Validation Report: unify-content-workflows-agentic-surfaces

**Date**: 2026-07-16
**Validation target**: `aa132239` plus the committed `protobufjs` security override
**Branch**: `openspec/unify-content-workflows-agentic-surfaces`

## Smoke Tests

**Status**: pass

- GitHub's cold-start migration and API boot check passed on the feature branch.
- The canonical API contract suite passed 18/18 tests.
- The feature-specific source and cross-interface workflow matrix passed 198/198 tests against PostgreSQL.
- The live local API started successfully and served the canonical OpenAPI surface during ZAP validation.

## Security

**Status**: pass

- `pnpm audit --audit-level high` reports no high or critical findings after pinning transitive `protobufjs` to `8.4.1`; three moderate findings remain below the configured merge threshold.
- OWASP Dependency-Check reports no high or critical findings. It reports two medium advisories in the OpenTelemetry/protobuf dependency chain.
- ZAP API scan against the local-only canonical OpenAPI server produced 117 passing rules, zero failures, and two low warnings: one environment-dependent 500 response and missing `Cross-Origin-Resource-Policy` headers.
- GitHub dependency audits and secret scanning passed before the dependency override and will rerun on the patched lockfile.

## E2E Tests

**Status**: pass

- The canonical workflow-surface Playwright scenario passed in Chromium.
- The summary review Playwright suite passed 8/8 scenarios in Chromium.
- The source matrix verifies every registered source through persisted podcast context across CLI, HTTP, and MCP contracts.

## Additional Gates

- Frontend unit tests: 51/51 passed.
- Frontend TypeScript check: passed.
- Frontend production build and generated workflow contract check: passed.
- OpenAPI and generated workflow contracts are current.

## Result

**PASS** - Local smoke, security, and E2E gates pass at the configured high-severity threshold. Merge remains conditional on the fresh GitHub CI run for the patched PR head.
