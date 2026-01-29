## Context
The application has 10 routes, dialog-based workflows, a review system, and background task tracking. Existing E2E tests are minimal and require a live backend. We need fast, deterministic tests that run in CI without infrastructure dependencies.

## Goals / Non-Goals
- Goals:
  - Full page coverage across all 10 routes
  - API mocking via Playwright route interception (no backend needed)
  - Page Object pattern for maintainability
  - Typed mock data factories matching backend API shapes
  - WCAG 2.0 AA accessibility testing via axe-core
  - Mobile viewport testing (3 browser projects)
  - Separate smoke suite for real-backend integration testing
- Non-Goals:
  - Visual regression testing (out of scope)
  - API contract testing (separate change)
  - Performance benchmarking

## Decisions

### API Mocking Strategy: Playwright route interception
- **Decision**: Use `page.route('**/api/v1/**', ...)` for all API mocking
- **Why**: No extra dependencies, runs in-process, deterministic, supports delay/error simulation
- **Alternatives considered**: MSW (Mock Service Worker) — adds complexity and extra dependency; separate mock server — slower, harder to maintain

### Page Object Pattern: Lightweight classes with Playwright fixtures
- **Decision**: Page objects injected via `test.extend<Fixtures>()` custom fixtures
- **Why**: Type-safe, auto-instantiated per test, follows Playwright best practices
- **Alternatives considered**: Helper functions (less organized); full POM framework (over-engineered)

### Mock Data Factories: TypeScript factory functions
- **Decision**: Factory functions with `Partial<T>` overrides matching `web/src/types/`
- **Why**: Type-safe, composable, co-located with tests, easy to customize per test
- **Alternatives considered**: JSON fixtures (no type safety); faker.js (random data breaks determinism)

### Accessibility Testing: axe-core via @axe-core/playwright
- **Decision**: WCAG 2.0 AA audit on every page with mocked data
- **Why**: Industry standard, maintained by Deque, Playwright integration available
- **Alternatives considered**: manual ARIA checks (insufficient coverage)

## Risks / Trade-offs
- **Mock drift**: API mocks may drift from real backend responses → Mitigation: types are shared, smoke tests validate real API
- **Test maintenance**: ~51 new files require ongoing maintenance → Mitigation: page objects isolate DOM changes, factory functions centralize data
- **False positives**: Mocked tests may pass when real integration fails → Mitigation: separate smoke suite validates critical paths with real backend

## Open Questions
- None — design is straightforward test-only addition
