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
uv pip install -e ".[dev]"
```
