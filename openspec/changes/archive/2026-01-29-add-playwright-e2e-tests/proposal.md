# Change: Add Comprehensive Playwright E2E Test Suite

## Why
The existing E2E test setup (2 files, 17 tests) hits the real API and fails without a running backend. We need a comprehensive, self-contained test suite that validates all pages, user flows, mobile behavior, accessibility, and error states using API mocking for deterministic, fast execution.

## What Changes
- Add shared test infrastructure: mock data factories, API route interception, page objects
- Add ~37 test files covering all 10 routes, dialogs, detail views, generation flows, review system
- Add cross-cutting tests: empty states, error states, loading states, background tasks, accessibility (axe-core)
- Add integration smoke tests (tagged `@smoke`, requires real backend)
- Update `playwright.config.ts` with timeouts, video-on-CI, and smoke project
- Install `@axe-core/playwright` devDependency

## Impact
- Affected specs: e2e-testing (new capability)
- Affected code: `web/tests/e2e/`, `web/playwright.config.ts`, `web/package.json`
- No production code changes — test-only addition
- All existing tests remain functional (backward compatible)
