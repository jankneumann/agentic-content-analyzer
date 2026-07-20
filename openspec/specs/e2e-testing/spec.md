# e2e-testing Specification

## Purpose
TBD - created by archiving change add-playwright-e2e-tests. Update Purpose after archive.
## Requirements
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

### Requirement: Registry-generated vertical source coverage

CI SHALL execute a deterministic vertical contract for every registry descriptor covering fixture ingestion, canonical content persistence, persisted summarization, resolved workflow selection, digest persistence, and podcast context assembly. Registry and fixture key sets MUST be equal. The dynamically routed `url` descriptor SHALL cover webpage, YouTube video, YouTube playlist, RSS, and forced-webpage variants.

#### Scenario: Every source reaches podcast context
- **WHEN** vertical source contracts run
- **THEN** each registered source produces eligible canonical summarized content
- **AND** that content can be persisted in a digest and exposed to podcast generation
- **AND** each URL routing variant reports the same normalized command and resolved-route fields across interfaces

#### Scenario: Missing source fixture fails CI
- **WHEN** a registry descriptor has no vertical fixture
- **THEN** contract collection fails before tests execute
- **AND** the missing canonical key is reported

### Requirement: Mixed-source provenance coverage

CI SHALL cover all source pairs, the `gmail/rss/substack` triple, and the `scholar_search/arxiv_search/huggingface_papers` triple using deterministic fixtures. Every case MUST assert canonical counts and provenance invariants.

#### Scenario: Pairwise source matrix
- **WHEN** the pairwise matrix runs
- **THEN** every pair completes ingestion through podcast context assembly
- **AND** duplicate cross-source content contributes one canonical summarized item

#### Scenario: High-risk triples preserve filters
- **WHEN** either declared high-risk triple runs with a source-filtered digest
- **THEN** themes, digest sources, and podcast available IDs contain only the selected canonical items

### Requirement: Cross-interface conformance coverage

CI SHALL submit representative commands through direct application services, CLI JSON mode, HTTP, MCP HTTP mode, MCP in-process mode, and the frontend API client. Equivalent inputs MUST validate against the same operation, problem, capability, and resource schemas.

#### Scenario: Operation contracts match across interfaces
- **WHEN** an equivalent digest request is submitted through every interface
- **THEN** submission and terminal operation payloads conform to the same schemas
- **AND** every successful result identifies a persisted digest

#### Scenario: Invalid ingestion command matches across interfaces
- **WHEN** the same unsupported source option is submitted through every interface
- **THEN** each rejects it before enqueueing
- **AND** error codes and field paths are semantically equivalent

### Requirement: Workflow edge-case coverage

The end-to-end suite SHALL cover duplicate aliases, null dates, explicit ingestion-date selection, filtered and failed content, missing summaries, force reprocessing, partial source failure, idempotent resubmission, cancellation, retry, and version 1 queue-drain compatibility.

#### Scenario: Duplicate and null-date edge cases
- **WHEN** mixed fixtures contain aliases and null publication dates
- **THEN** default workflow resolution excludes them with structured reasons
- **AND** explicit ingestion-date selection includes only otherwise eligible null-date records

#### Scenario: Retry remains idempotent
- **WHEN** a resource-producing operation fails after resource reservation and is retried
- **THEN** the retry completes or updates the reserved resource
- **AND** it does not create a second logical resource
