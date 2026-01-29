## ADDED Requirements

### Requirement: E2E Test Infrastructure
The test suite SHALL provide shared infrastructure for writing deterministic E2E tests without a running backend.

#### Scenario: Mock data factories produce typed responses
- **WHEN** a test calls a factory function (e.g., `createContentListItem()`)
- **THEN** it returns a fully-typed object matching the API response shape (snake_case fields)
- **AND** optional `Partial<T>` overrides allow customization

#### Scenario: API mocks intercept all endpoints
- **WHEN** `ApiMocks.mockAllDefaults()` is called
- **THEN** all `/api/v1/*` endpoints return realistic mock data
- **AND** no real network requests are made to the backend

#### Scenario: Page objects encapsulate DOM interactions
- **WHEN** a test uses a page object (e.g., `contentsPage.searchFor("GPT")`)
- **THEN** the interaction is executed via Playwright locators
- **AND** the page object provides typed access to page elements

### Requirement: Page Coverage
The test suite SHALL cover all application routes with mocked API data.

#### Scenario: Every route has at least one test file
- **WHEN** the test suite runs
- **THEN** tests exist for all 10 routes: dashboard, contents, summaries, digests, scripts, podcasts, audio-digests, themes, review, settings

#### Scenario: List pages test filtering and sorting
- **WHEN** a list page test runs
- **THEN** it validates table rendering, search filtering, dropdown filters, column sorting, and pagination

#### Scenario: Detail dialogs test content display
- **WHEN** a detail dialog test runs
- **THEN** it validates dialog opens, content sections render, metadata displays, and dialog closes on X/Escape

#### Scenario: Generation dialogs test form submission
- **WHEN** a generation dialog test runs
- **THEN** it validates dialog opens, parameters configured, form submits, and dialog closes

### Requirement: Cross-Cutting Behavior Tests
The test suite SHALL validate empty states, error states, loading states, and background task behavior.

#### Scenario: Empty states display correctly
- **WHEN** the API returns empty data for any page
- **THEN** the page displays an appropriate empty state UI

#### Scenario: Error states display correctly
- **WHEN** the API returns a 500 error
- **THEN** the page displays error UI with a retry option

#### Scenario: Loading states display correctly
- **WHEN** the API response is delayed
- **THEN** the page displays skeleton loaders during the delay

### Requirement: Accessibility Testing
The test suite SHALL validate WCAG 2.0 AA compliance on every page.

#### Scenario: No critical accessibility violations
- **WHEN** axe-core scans a page with mocked data
- **THEN** zero critical or serious violations are reported

### Requirement: Mobile Viewport Testing
All tests SHALL run on Desktop Chrome, Mobile Chrome (Pixel 7), and Mobile Safari (iPhone 14).

#### Scenario: Responsive layout adapts correctly
- **WHEN** a test runs on mobile viewport
- **THEN** the sidebar is hidden, hamburger menu is available, and safe area padding is applied

### Requirement: Smoke Integration Tests
A separate test suite SHALL validate critical flows against a real backend.

#### Scenario: Smoke tests require real backend
- **WHEN** the smoke suite runs
- **THEN** it hits the real API (no mocking) and validates dashboard loads, data fetches, and navigation works

#### Scenario: Smoke tests are excluded from default run
- **WHEN** `pnpm test:e2e` runs
- **THEN** smoke tests are not included (requires explicit `--project=smoke`)
