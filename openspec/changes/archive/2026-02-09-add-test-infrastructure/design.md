# Design: Test Infrastructure

## Context

Tests currently use ad-hoc fixtures and mocking patterns. As the codebase grows, we need standardized infrastructure for reliable, maintainable tests.

## Goals

1. Standardized model factories
2. Database isolation per test
3. Clear test taxonomy (unit/integration/e2e)
4. Integration with Hoverfly for HTTP simulation

## Relationship to Hoverfly Proposal

```
┌─────────────────────────────────────────────────────────────────────┐
│ add-test-infrastructure (this proposal)                             │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Model Factories  │  │ DB Fixtures      │  │ Test Organization│  │
│  │ - ContentFactory │  │ - Session mgmt   │  │ - unit/          │  │
│  │ - SummaryFactory │  │ - Transaction    │  │ - integration/   │  │
│  │ - DigestFactory  │  │   rollback       │  │ - e2e/           │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ add-hoverfly-api-simulation (separate proposal)              │   │
│  │ - HTTP proxy for external APIs                               │   │
│  │ - Simulation recordings for RSS, LLM, TTS                    │   │
│  │ - Test-time proxy configuration                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Factory Boy for Model Factories

**What**: Use `factory_boy` for test data generation.

**Why**: Declarative, composable, widely adopted.

```python
# tests/factories/content.py
import factory
from src.models.content import Content, ContentSource, ContentStatus

class ContentFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Content
        sqlalchemy_session_persistence = "commit"

    title = factory.Faker("sentence")
    source_type = ContentSource.RSS
    status = ContentStatus.COMPLETED
    markdown_content = factory.Faker("text", max_nb_chars=1000)
    content_hash = factory.LazyAttribute(
        lambda o: generate_markdown_hash(o.markdown_content)
    )

    class Params:
        pending = factory.Trait(
            status=ContentStatus.PENDING,
            markdown_content=None
        )
        with_audio = factory.Trait(
            audio_url=factory.Faker("url")
        )
```

### Decision 2: Transaction Rollback for DB Isolation

**What**: Each test runs in a transaction that rolls back.

**Why**: Fast, isolated, no cleanup needed.

```python
# tests/conftest.py
@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### Decision 3: Test Taxonomy with Markers

**What**: Categorize tests with pytest markers.

```python
@pytest.mark.unit
def test_parse_markdown():
    """Pure unit test - no external dependencies"""
    pass

@pytest.mark.integration
def test_content_service_create(db_session):
    """Integration test - requires database"""
    pass

@pytest.mark.e2e
def test_api_create_content(client):
    """End-to-end test - full API request"""
    pass

@pytest.mark.slow
def test_large_digest_creation():
    """Slow test - excluded from quick runs"""
    pass
```

### Decision 4: Fixture Organization

**What**: Centralized fixture files by domain.

```
tests/
├── conftest.py              # Global fixtures (db_session, client)
├── factories/
│   ├── __init__.py
│   ├── content.py           # ContentFactory, SummaryFactory
│   ├── digest.py            # DigestFactory
│   └── user.py              # Future: UserFactory
├── fixtures/
│   ├── markdown/            # Sample markdown files
│   ├── html/                # Sample HTML for parsing
│   └── api_responses/       # Mock API response data
```

### Decision 5: Hoverfly Integration Points

**What**: Configure tests to use Hoverfly when available.

```python
# tests/conftest.py
@pytest.fixture
def http_client(hoverfly_url):
    """HTTP client configured for Hoverfly proxy."""
    if hoverfly_url:
        return httpx.Client(proxies=hoverfly_url)
    return httpx.Client()

# Usage in integration tests
@pytest.mark.integration
def test_rss_ingestion(http_client, db_session):
    service = RSSIngestionService(http_client=http_client)
    # Hoverfly returns recorded response
    content = service.fetch_feed("https://example.com/feed.xml")
```

### Decision 6: CI Test Configuration

**What**: Run different test categories in CI.

```yaml
# .github/workflows/ci.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -m unit

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres: ...
      hoverfly: ...
    steps:
      - run: pytest -m integration

  e2e-tests:
    runs-on: ubuntu-latest
    services:
      postgres: ...
      redis: ...
    steps:
      - run: pytest -m e2e
```

## File Structure

```
tests/
├── conftest.py                 # Global fixtures
├── factories/
│   ├── __init__.py
│   ├── content.py
│   ├── digest.py
│   └── summary.py
├── fixtures/
│   ├── markdown/
│   │   ├── sample_content.md
│   │   └── sample_summary.md
│   └── api_responses/
│       ├── anthropic/
│       └── rss/
├── unit/                       # Pure unit tests
│   ├── test_markdown_utils.py
│   └── test_content_hash.py
├── integration/                # Component integration
│   ├── test_content_service.py
│   └── test_summarizer.py
└── e2e/                        # Full API tests
    ├── test_content_api.py
    └── test_digest_api.py
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Slow integration tests | Run in parallel, use markers to skip |
| Factory complexity | Start simple, add traits as needed |
| Hoverfly simulation drift | Periodically refresh recordings |
