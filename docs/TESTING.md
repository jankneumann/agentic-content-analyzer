# Testing Guide

This guide covers the testing infrastructure, patterns, and best practices for the newsletter aggregator project.

## Quick Reference

```bash
# Run all tests (excludes integration and live_api by default)
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test categories
pytest -m unit                    # Pure unit tests
pytest -m integration             # Database integration tests
pytest -m hoverfly                # Hoverfly HTTP simulation tests
pytest -m "not slow"              # Skip slow tests
pytest -m live_api                # Tests calling real APIs (costs money!)

# Run specific test files
pytest tests/unit/test_factories.py -v
pytest tests/api/test_digest_api.py -v
```

## Test Categories

Tests are organized by category using pytest markers:

| Marker | Description | Dependencies |
|--------|-------------|--------------|
| `unit` | Pure unit tests | None |
| `integration` | Database integration | PostgreSQL test database |
| `hoverfly` | HTTP simulation tests | Hoverfly (`make hoverfly-up`) |
| `e2e` | End-to-end API tests | PostgreSQL, may mock external APIs |
| `slow` | Tests > 1 second | Varies |
| `live_api` | Calls real external APIs | API keys, costs money |
| `crawl4ai` | Requires Crawl4AI setup | Browser, Crawl4AI |

Default test run excludes `integration` and `live_api` tests.

## Test Database Setup

Integration tests require a PostgreSQL test database:

```bash
# Create test database
createdb newsletters_test

# Or using psql
psql -c "CREATE DATABASE newsletters_test;"

# Grant permissions (if using newsletter_user)
psql -c "GRANT ALL PRIVILEGES ON DATABASE newsletters_test TO newsletter_user;"
```

Set the test database URL:

```bash
# .env or environment
TEST_DATABASE_URL=postgresql://newsletter_user:newsletter_password@localhost/newsletters_test
```

**Important:** The test database name must contain "test" as a safety check to prevent accidentally running tests against production.

## Factory Boy Usage

The project uses [Factory Boy](https://factoryboy.readthedocs.io/) for test data generation.

### Available Factories

| Factory | Model | Key Traits |
|---------|-------|------------|
| `ContentFactory` | `Content` | `pending`, `completed`, `youtube`, `gmail`, `rss`, `file_upload`, `with_audio`, `failed` |
| `SummaryFactory` | `Summary` | `minimal`, `openai`, `high_relevance`, `low_relevance` |
| `DigestFactory` | `Digest` | `daily`, `weekly`, `pending`, `completed`, `pending_review`, `approved`, `delivered`, `with_sources`, `combined` |

### Basic Usage

```python
from tests.factories import ContentFactory, SummaryFactory, DigestFactory

# Build without database (returns model instance, no DB write)
content = ContentFactory.build()

# Build with traits
pending_content = ContentFactory.build(pending=True)
youtube_content = ContentFactory.build(youtube=True)

# Combine traits
youtube_pending = ContentFactory.build(youtube=True, pending=True)
```

### With Database (Integration Tests)

```python
import pytest

@pytest.mark.integration
def test_content_persistence(db_session, content_factory):
    # Factory is bound to db_session via conftest.py
    content = content_factory.create()

    assert content.id is not None

    # Create multiple
    contents = content_factory.create_batch(5, youtube=True)
    assert len(contents) == 5
```

### Overriding Fields

```python
# Override specific fields
content = ContentFactory.build(
    title="Custom Title",
    author="Custom Author",
    published_date=datetime(2025, 1, 15)
)

# Combine with traits
content = ContentFactory.build(
    youtube=True,
    title="Custom YouTube Video"
)
```

### SubFactory Relationships

`SummaryFactory` automatically creates a `Content` via `SubFactory`:

```python
# Summary with auto-created content
summary = SummaryFactory.build()
assert summary.content is not None

# Summary for specific content
content = ContentFactory.build()
summary = SummaryFactory.build(content=content)
```

## Test Fixtures

### Sample Data Files

Sample test data is available in `tests/fixtures/`:

```
tests/fixtures/
├── markdown/
│   ├── sample_content.md    # Sample newsletter content
│   ├── sample_summary.md    # Sample summary
│   └── sample_digest.md     # Sample digest
├── html/
│   └── sample_newsletter.html  # Sample HTML newsletter
└── json/
    └── (future JSON fixtures)
```

### Loading Fixtures

```python
from tests.fixtures import load_markdown, load_html, load_fixture

# Load by type
content_md = load_markdown("sample_content.md")
newsletter_html = load_html("sample_newsletter.html")

# Load by path
digest = load_fixture("markdown/sample_digest.md")

# List available fixtures
from tests.fixtures import list_fixtures
print(list_fixtures("markdown"))  # ['sample_content.md', 'sample_digest.md', ...]
```

### Direct Path Access

```python
from tests.fixtures import SAMPLE_CONTENT_MD, SAMPLE_NEWSLETTER_HTML

# Use Path objects directly
content = SAMPLE_CONTENT_MD.read_text()
```

## Database Fixtures

### Session Fixture

The `db_session` fixture provides a database session with transaction rollback:

```python
@pytest.mark.integration
def test_with_database(db_session):
    # All changes are rolled back after test
    content = Content(...)
    db_session.add(content)
    db_session.commit()
    # Rolled back automatically
```

### API Client Fixture

The `client` fixture provides a FastAPI TestClient with database override:

```python
def test_api_endpoint(client, db_session):
    # Create test data
    # ... factory or manual setup ...

    # Make API request
    response = client.get("/api/v1/digests/")
    assert response.status_code == 200
```

## Writing Tests

### Unit Test Example

```python
# tests/unit/test_example.py
import pytest
from tests.factories import ContentFactory

class TestContentValidation:
    def test_content_hash_is_computed(self):
        """Content hash should be SHA-256 of markdown."""
        import hashlib

        content = ContentFactory.build()
        expected = hashlib.sha256(content.markdown_content.encode()).hexdigest()

        assert content.content_hash == expected

    def test_youtube_content_has_video_metadata(self):
        """YouTube content should include video metadata."""
        content = ContentFactory.build(youtube=True)

        assert "video_duration_seconds" in content.metadata_json
```

### Integration Test Example

```python
# tests/integration/test_content_service.py
import pytest
from tests.factories import ContentFactory

@pytest.mark.integration
class TestContentService:
    def test_create_content(self, db_session, content_factory):
        """Service should persist content to database."""
        content = content_factory.create()

        # Query back
        from src.models.content import Content
        result = db_session.query(Content).get(content.id)

        assert result is not None
        assert result.title == content.title

    def test_duplicate_detection(self, db_session, content_factory):
        """Service should detect duplicate content by hash."""
        content1 = content_factory.create()
        content2 = content_factory.build(content_hash=content1.content_hash)

        # Should detect as duplicate
        # ... test service logic ...
```

### API Test Example

```python
# tests/api/test_digest_api.py
import pytest

class TestDigestAPI:
    def test_list_digests(self, client, db_session):
        """GET /api/v1/digests/ should return digest list."""
        from tests.factories import DigestFactory
        DigestFactory._meta.sqlalchemy_session = db_session

        # Create test data
        DigestFactory.create_batch(3)
        db_session.commit()

        # Make request
        response = client.get("/api/v1/digests/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
```

## Best Practices

### 1. Use Factories Over Manual Setup

```python
# ❌ Avoid: Manual object construction
content = Content(
    source_type=ContentSource.RSS,
    source_id="test-1",
    title="Test",
    markdown_content="...",
    content_hash="...",
    status=ContentStatus.COMPLETED,
    # ... many more fields
)

# ✅ Prefer: Factory with traits
content = ContentFactory.build(rss=True, completed=True)
```

### 2. Use Traits for Variations

```python
# ❌ Avoid: Manually setting status
content = ContentFactory.build()
content.status = ContentStatus.PENDING

# ✅ Prefer: Use trait
content = ContentFactory.build(pending=True)
```

### 3. Mark Integration Tests

```python
# ✅ Always mark tests that need external resources
@pytest.mark.integration
def test_database_operation(db_session):
    ...

@pytest.mark.live_api
def test_real_api_call():
    ...
```

### 4. Use Fixtures for Shared Setup

```python
# ✅ Define reusable fixtures
@pytest.fixture
def content_with_summary(db_session, content_factory, summary_factory):
    content = content_factory.create()
    summary = summary_factory.create(content=content)
    return content, summary
```

### 5. Test One Thing Per Test

```python
# ❌ Avoid: Testing multiple behaviors
def test_content_operations():
    # Creates, updates, and deletes in one test

# ✅ Prefer: Separate tests
def test_content_creation():
    ...

def test_content_update():
    ...

def test_content_deletion():
    ...
```

## Running Specific Tests

```bash
# By file
pytest tests/unit/test_factories.py

# By class
pytest tests/unit/test_factories.py::TestContentFactory

# By test name pattern
pytest -k "test_youtube"

# By marker
pytest -m "unit and not slow"

# With verbose output
pytest tests/api/ -v

# Stop on first failure
pytest --exitfirst

# Run last failed tests
pytest --lf
```

## Coverage

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html

# Coverage for specific module
pytest --cov=src.models tests/test_models/
```

## Troubleshooting

### Database Connection Errors

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:** Ensure PostgreSQL is running and test database exists:
```bash
docker compose up -d  # If using Docker
createdb newsletters_test
```

### Test Database Safety Check Failed

```
ValueError: Safety check failed: Database 'newsletters' does not contain 'test'
```

**Solution:** Set `TEST_DATABASE_URL` to a database with "test" in the name.

### Factory Session Not Set

```
RuntimeError: No session provided to SQLAlchemy factory
```

**Solution:** Ensure `db_session` fixture is used, which configures factory sessions.

### Import Errors in Tests

```
ModuleNotFoundError: No module named 'src'
```

**Solution:** Install the package in development mode:
```bash
uv sync --all-extras
```

---

## Integration Test Fixtures

Integration test fixtures live in `tests/integration/fixtures/` and share configuration patterns.

### Configuration via Settings

**All integration test fixtures must access environment configuration through `get_settings()`**, not `os.getenv()` or `os.environ.get()`. This ensures fixtures honor the full Settings precedence chain (env vars > profiles > `.secrets.yaml` > `.env` > defaults).

```python
# ✅ Correct: Use Settings
from src.config.settings import get_settings

settings = get_settings()
url = settings.hoverfly_admin_url  # Respects profiles, .env, defaults

# ❌ Wrong: Direct env var access
import os
url = os.getenv("HOVERFLY_ADMIN_URL", "http://localhost:8888")  # Bypasses profiles
```

### Available Fixture Modules

| Module | Purpose | Skip Condition |
|--------|---------|----------------|
| `fixtures/hoverfly.py` | HTTP API simulation via Hoverfly | Hoverfly not running |
| `fixtures/neon.py` | Ephemeral Neon database branches | `NEON_API_KEY` not set |
| `fixtures/opik.py` | Opik observability provider testing | Opik stack not running |
| `fixtures/supabase.py` | Supabase database connection testing | Supabase credentials not set |

All fixture modules are imported in `tests/integration/conftest.py` and available to all integration tests.

### Adding New Fixture Modules

1. Create `tests/integration/fixtures/my_service.py`
2. Use `get_settings()` for all configuration (add Settings fields if needed)
3. Provide an `available` fixture (session-scoped bool) and a `requires_*` skip marker
4. Import fixtures in `tests/integration/conftest.py`

---

## Hoverfly API Simulation

Hoverfly provides HTTP-level integration testing by acting as a simulated webserver. Unlike unit test mocks that patch at the Python level, Hoverfly tests real HTTP behavior: headers, content negotiation, status codes, and response formats.

### Quick Start

```bash
make hoverfly-up       # Start Hoverfly in webserver mode
make test-hoverfly     # Run Hoverfly tests
make hoverfly-down     # Stop Hoverfly
```

### Architecture

Hoverfly runs in **webserver mode** (`-webserver` flag in `docker-compose.yml`):
- It IS the HTTP destination — no upstream server needed
- Admin API on port 8888 (simulation management)
- Webserver on port 8500 (handles test requests)
- Docker image pinned to `spectolabs/hoverfly:v1.10.5`

### Key Files

| File | Purpose |
|------|---------|
| `tests/helpers/hoverfly.py` | `HoverflyClient` — admin API wrapper (import/reset/export simulations) |
| `tests/helpers/test_hoverfly.py` | Unit tests for HoverflyClient (uses `responses` library, no Hoverfly needed) |
| `tests/integration/fixtures/hoverfly.py` | Pytest fixtures (`hoverfly`, `hoverfly_url`, `hoverfly_available`, `requires_hoverfly`) |
| `tests/integration/fixtures/simulations/` | JSON simulation files (Hoverfly v5 schema) |
| `tests/integration/test_hoverfly_rss.py` | Integration tests for RSS feed simulation |

### Writing Tests

```python
from pathlib import Path
import httpx
import pytest

SIMULATIONS_DIR = Path(__file__).parent / "fixtures" / "simulations"

@pytest.mark.hoverfly
@pytest.mark.integration
def test_feed_returns_xml(hoverfly, hoverfly_url):
    hoverfly.import_simulation(SIMULATIONS_DIR / "rss_feed.json")
    response = httpx.get(f"{hoverfly_url}/feed")
    assert response.status_code == 200
    assert "application/rss+xml" in response.headers["content-type"]
```

### Creating Simulations

Simulations are JSON files in `tests/integration/fixtures/simulations/`. See `tests/integration/README.md` for the full guide including capture mode instructions.

### Gotchas

| Issue | Solution |
|-------|----------|
| Webserver mode has no capture | Must restart in proxy mode (remove `-webserver` flag) for capture — see integration README |
| Tests must not depend on execution order | Each test should load its own simulation; fixture teardown resets simulations |
| HoverflyClient uses `Connection: close` header | Prevents connection pooling issues with httpx in test contexts |
| Settings fields have real defaults | `hoverfly_proxy_url` defaults to `http://localhost:8500`, `hoverfly_admin_url` to `http://localhost:8888` |

### Crawl4AI Integration Tests

Tests requiring a Crawl4AI browser server use the `@pytest.mark.crawl4ai` marker:

```bash
make crawl4ai-up      # Start Crawl4AI Docker server
make test-crawl4ai    # Run Crawl4AI integration tests
make crawl4ai-down    # Stop server
```

**Fixtures** (defined in `tests/integration/fixtures/crawl4ai.py`):
- `crawl4ai_available` — session-scoped, True if server is running
- `requires_crawl4ai` — autouse marker, skips tests if server is down
- `crawl4ai_url` — base URL for the Crawl4AI server

**Hoverfly simulations** for Crawl4AI remote mode:
- `tests/integration/fixtures/simulations/crawl4ai_md_success.json` — successful `POST /md`
- `tests/integration/fixtures/simulations/crawl4ai_md_error.json` — server error response

---

## E2E Testing (Playwright)

The frontend has a comprehensive Playwright E2E test suite covering all pages, dialogs, navigation, accessibility, and error states.

### Quick Reference

```bash
cd web

# Run all E2E tests (API mocked, no backend needed)
pnpm test:e2e

# Run specific project
pnpm exec playwright test --project=chromium
pnpm exec playwright test --project="Mobile Chrome"
pnpm exec playwright test --project="Mobile Safari"

# Run specific test folder or file
pnpm exec playwright test tests/e2e/layout/
pnpm exec playwright test tests/e2e/review/digest-review.spec.ts

# Visual Playwright inspector (debug mode)
pnpm test:e2e:ui

# Run smoke tests (requires real backend running)
pnpm test:e2e:smoke

# View HTML report after a run
pnpm exec playwright show-report
```

### Test Architecture

Tests are organized by domain with shared infrastructure:

```
web/tests/e2e/
├── fixtures/                     # Shared test infrastructure
│   ├── index.ts                  # Custom test export with fixtures
│   ├── base.page.ts              # Base page object (sidebar, header)
│   ├── api-mocks.ts              # ApiMocks class (route interception)
│   ├── mock-data.ts              # Typed response factories
│   └── pages/*.page.ts           # Page objects (10 pages)
├── layout/                       # Navigation, responsive, theme toggle
├── dashboard/                    # Dashboard stats, quick actions
├── contents/                     # List, detail dialog, ingest dialog
├── summaries/                    # List, detail, generate
├── digests/                      # List, detail, generate, review
├── scripts/                      # List, detail, generate, review
├── podcasts/                     # List, player, generate
├── audio-digests/                # List, player, generate
├── themes/                       # Analysis page, analyze dialog
├── review/                       # Queue, digest/summary/script review
├── cross-cutting/                # Accessibility, errors, loading, empty states
├── smoke/                        # Integration tests (real backend)
├── pwa.spec.ts                   # PWA manifest, offline, service worker
└── generation-dialogs.spec.ts    # Generation dialog user flows
```

### Playwright Projects

| Project | Purpose | API Mocking | Backend Required |
|---------|---------|-------------|------------------|
| `chromium` | Desktop Chrome (default) | Yes | No |
| `Mobile Chrome` | Pixel 7 viewport | Yes | No |
| `Mobile Safari` | iPhone 14 viewport | Yes | No |
| `smoke` | Integration smoke tests | No | **Yes** |

Default projects exclude smoke tests via `grepInvert: /@smoke/`.

### API Mocking Strategy

All non-smoke tests use **Playwright route interception** for deterministic, fast tests:

```typescript
import { test, expect } from "../fixtures"

test.describe("My Feature", () => {
  test.beforeEach(async ({ apiMocks }) => {
    // Mock ALL API endpoints with default data
    await apiMocks.mockAllDefaults()
  })

  test("renders data", async ({ page, contentsPage }) => {
    await contentsPage.navigate()
    await expect(page.getByRole("table")).toBeVisible()
  })
})
```

**Key `ApiMocks` methods:**
- `mockAllDefaults()` — Mocks all endpoints with realistic data
- `mockAllEmpty()` — Returns empty lists/zero counts (for empty state tests)
- `mockAllErrors()` — Returns 500 errors (for error state tests)
- `mockWithError(pattern, status, message)` — Mock specific endpoint with error
- Individual methods: `mockContentsList()`, `mockDigestDetail()`, etc.

### Page Object Pattern

Page objects encapsulate locators and common actions:

```typescript
import { test, expect } from "../fixtures"

test("contents page loads", async ({ contentsPage, apiMocks }) => {
  await apiMocks.mockAllDefaults()
  await contentsPage.navigate()  // Uses BasePage.goto("/contents")

  await expect(contentsPage.table).toBeVisible()
  await expect(contentsPage.searchInput).toBeVisible()
})
```

### Mock Data Factories

Typed factories in `fixtures/mock-data.ts` match API response shapes:

```typescript
import * as mockData from "../fixtures/mock-data"

// Create with defaults
const content = mockData.createContent()

// Override specific fields
const custom = mockData.createContentListItem({
  title: "Custom Title",
  status: "pending",
})

// Create list responses
const listResponse = mockData.createContentListResponse({ total: 50 })
```

### Writing New Tests

1. **Import from fixtures**, not `@playwright/test`:
   ```typescript
   import { test, expect } from "../fixtures"
   ```

2. **Always mock APIs** in `beforeEach`:
   ```typescript
   test.beforeEach(async ({ apiMocks }) => {
     await apiMocks.mockAllDefaults()
   })
   ```

3. **Use semantic locators** — prefer `getByRole()` over `getByText()`:
   ```typescript
   // ✅ Good — specific, resilient
   page.getByRole("heading", { name: "Dashboard", level: 1 })
   page.getByRole("button", { name: /generate/i })

   // ❌ Avoid — matches substrings, ambiguous
   page.getByText("Dashboard")
   page.locator(".my-class")
   ```

4. **Handle strict mode** — Playwright rejects locators matching multiple elements:
   ```typescript
   // ✅ Scope to parent container
   page.locator("main").getByText("Content")

   // ✅ Use exact match
   page.getByText("Source", { exact: true })

   // ✅ Use .first() when multiple matches are expected
   page.getByRole("button", { name: /close/i }).first()
   ```

5. **Route patterns must handle query params** — add trailing `*`:
   ```typescript
   // ✅ Matches /api/v1/items/1/navigation?status=pending
   await page.route("**/api/v1/items/*/navigation*", handler)

   // ❌ Won't match URLs with query parameters
   await page.route("**/api/v1/items/*/navigation", handler)
   ```

6. **Mock data must be complete** — include all fields components access:
   ```typescript
   // ❌ Crashes: component does `obj.strategic_insights.length`
   { id: 1, title: "Item" }

   // ✅ Include arrays even if empty
   { id: 1, title: "Item", strategic_insights: [], technical_details: [] }
   ```

### Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| `getByText("Content")` matches "Ingest Content" | Use `{ exact: true }` or `getByRole("link", { name: "Content", exact: true })` |
| Sidebar text duplicates main content | Scope to `page.locator("main")` or `page.locator("aside")` |
| Dialog has 2 close buttons (X + text) | Use `.first()` on `getByRole("button", { name: /close/i })` |
| Route pattern misses query params | Add trailing `*`: `**/api/v1/path*` |
| Mock missing array fields → crash | Components accessing `.length` on undefined throw; include all array fields |
| Smoke tests fail without backend | Expected — smoke tests excluded from default projects via `grepInvert` |
| PWA manifest returns HTML in dev | VitePWA only serves manifest in production builds |
| Route handler not matching | Routes are LIFO — register specific patterns AFTER general ones |
| Stats cards text matches table badges | Scope stats assertions to `.grid` container: `page.locator(".grid").first()` |

### Accessibility Testing

All pages are audited with `@axe-core/playwright` for WCAG 2.0 AA:

```typescript
import AxeBuilder from "@axe-core/playwright"

const results = await new AxeBuilder({ page })
  .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
  .analyze()

const violations = results.violations.filter(
  (v) => v.impact === "critical" || v.impact === "serious"
)
expect(violations).toEqual([])
```

**Disabled rules** (known app-level issues, not test bugs):
- `heading-order` — Heading levels not sequential in some layouts
- `button-name` — Some icon-only buttons lack discernible text
- `scrollable-region-focusable` — Main scrollable region needs tabIndex
