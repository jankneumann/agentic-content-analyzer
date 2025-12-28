# Development Guide

## Development Commands

### Ingestion

```bash
# Fetch newsletters from Gmail
python -m src.ingestion.gmail

# Fetch newsletters from Substack RSS feeds
python -m src.ingestion.substack

# Force reprocess existing newsletters
python -m src.ingestion.gmail --force
python -m src.ingestion.substack --force
```

### Processing

```bash
# Summarize a specific newsletter
python -m src.processors.summarizer --newsletter-id <id>

# Create a daily digest
python -m src.processors.digest_creator --type daily

# Create a weekly digest
python -m src.processors.digest_creator --type weekly
```

### Background Tasks (Celery)

```bash
# Start Celery worker for async processing
celery -A src.tasks worker --loglevel=info

# Start Celery beat scheduler for periodic tasks
celery -A src.tasks beat --loglevel=info

# Monitor tasks
celery -A src.tasks flower  # Web UI at localhost:5555
```

### API Server

```bash
# Start FastAPI development server
uvicorn src.api.app:app --reload

# API docs available at:
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

### Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/agents/claude/           # Test Claude SDK agents
pytest tests/test_config/             # Test configuration system
pytest tests/integration/             # Integration tests

# Run tests matching pattern
pytest -k "test_summarization"        # All summarization tests
pytest -k "test_cost"                 # All cost calculation tests

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_config/test_models.py -v
```

### Linting & Type Checking

```bash
# Lint code with Ruff
ruff check src/
ruff check src/ --fix  # Auto-fix issues

# Type check with mypy
mypy src/

# Format code
ruff format src/
```

### Database Management

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current migration status
alembic current

# View migration history
alembic history
```

## Development Guidelines

### Git Workflow

**CRITICAL**: Commit after every major feature implementation:
- Makes recovery from errors easy (e.g., reverting problematic changes)
- Provides clear checkpoints for progress tracking
- Use descriptive commit messages that explain the "why"
- Commit frequency: After completing each major task/feature

**Example workflow**:
```bash
# After completing feature/fix
git add .
git commit -m "Add integration tests for theme analysis workflow

- Created test fixtures for sample newsletters
- Added assertions for theme detection accuracy
- Verified historical context integration"
```

**Commit Message Best Practices**:
- Use imperative mood ("Add feature" not "Added feature")
- First line: concise summary (50 chars or less)
- Blank line, then detailed explanation if needed
- Reference issues: "Fixes #123" or "Relates to #456"

### Tool Usage Best Practices

#### AVOID sed for Global Changes

**CRITICAL**: `sed` can cause unintended side effects and is difficult to control precisely.

**Bad Example**:
```bash
# DON'T: This might remove commas from unintended places
sed -i 's/$/,/g' file.py  # Removed commas from JSON, function params, etc.
```

**Rules**:
- **NEVER use sed for global changes** unless very narrowly scoped
- **ALWAYS prefer the Edit tool** for code changes - it's safer and more precise
- Only use sed for extremely specific, well-tested patterns
- If in doubt, use Edit tool instead

**Good Alternative**:
```python
# DO: Use Edit tool with exact string matching
Edit(
    file_path="...",
    old_string="exact string to replace",
    new_string="exact replacement"
)
```

### Running Scripts

**Always activate virtual environment first**:
```bash
source .venv/bin/activate  # Required before running any Python scripts
python scripts/script_name.py
```

**Do NOT use**:
- `python3 scripts/...` without venv activation
- `PYTHONPATH=. python3 scripts/...` as a workaround

Why: Ensures correct dependencies, Python version, and package paths.

## Learning Goals

This project serves as a **comparison framework for agent development kits**:

- **Document developer experience** for each framework
- **Compare API design**, tool use, orchestration patterns
- **Benchmark performance** (speed, quality, token usage)
- **Analyze cost implications**
- **Identify strengths/weaknesses** for different use cases
- **Produce comprehensive comparison documentation**

### Framework Comparison Criteria

1. **API Design**: Ease of use, clarity, consistency
2. **Tool Use**: How each framework handles function calling
3. **Orchestration**: Multi-agent coordination patterns
4. **Performance**: Speed, accuracy, token efficiency
5. **Cost**: Actual costs per pipeline step
6. **Developer Experience**: Setup, debugging, documentation

## Architecture Patterns

### Client-Service Pattern

For data ingestion, use two-layer architecture:

**1. Client Layer** - Fetches/parses data from external source
- Classes: `GmailClient`, `SubstackRSSClient`
- Returns: `NewsletterData` (Pydantic model)
- No database interaction
- Pure data fetching and parsing

**2. Service Layer** - Business logic + database persistence
- Classes: `GmailIngestionService`, `SubstackIngestionService`
- Uses Client to fetch data
- Handles deduplication, database storage, error handling
- Returns count of ingested items

**Example**:
```python
# Client - data fetching only
client = SubstackRSSClient()
newsletters = client.fetch_feed(url)

# Service - business logic + persistence
service = SubstackIngestionService()
count = service.ingest_newsletters(feed_urls)
```

**Benefits**:
- Clear separation of concerns
- Client can be tested independently
- Service can be swapped (e.g., different databases)
- Reusable clients across different services

### Configuration Flexibility

Support multiple configuration methods for better UX:

- **Environment variables**: For simple cases, CI/CD
- **Config files**: For complex lists, better developer experience
- **Command-line arguments**: For one-off overrides

**Example** (RSS feeds):
```python
# Priority: CLI args > env var > config file
def get_rss_feed_urls(self) -> list[str]:
    feeds = []

    # 1. Environment variable (comma-separated)
    if self.rss_feeds:
        feeds.extend(self.rss_feeds.split(","))

    # 2. Config file (one per line)
    if os.path.exists(self.rss_feeds_file):
        with open(self.rss_feeds_file) as f:
            feeds.extend(line.strip() for line in f if line.strip())

    # Deduplicate while preserving order
    return list(dict.fromkeys(feeds))
```

## Database Patterns

### Deduplication

Always check for existing records before inserting:

```python
existing = db.query(Newsletter).filter(
    Newsletter.source_id == newsletter_data.source_id
).first()

if existing:
    if force_reprocess:
        # Update and reset status for reprocessing
        existing.status = ProcessingStatus.PENDING
        existing.raw_html = newsletter_data.raw_html
        existing.raw_text = newsletter_data.raw_text
        db.commit()
        logger.info(f"Reset for reprocessing: {existing.title}")
    else:
        logger.debug(f"Already exists: {existing.title}")
        continue  # Skip, already exists
else:
    # Create new record
    newsletter = Newsletter(**newsletter_data.dict())
    db.add(newsletter)
```

### Session Management

Use context managers for proper cleanup:

```python
with get_db() as db:
    # Database operations
    newsletter = Newsletter(...)
    db.add(newsletter)
    db.commit()
    # Auto-commits on success, rolls back on exception
```

**Benefits**:
- Automatic connection cleanup
- Transaction rollback on errors
- No resource leaks

### Force Reprocess Flag

Provide `--force` flag in CLI scripts for reprocessing:

```python
@click.command()
@click.option('--force', is_flag=True, help='Force reprocess existing newsletters')
def ingest(force: bool):
    service = GmailIngestionService(force_reprocess=force)
    count = service.ingest_newsletters()
```

**Use cases**:
- Testing: Reprocess sample data with code changes
- Iteration: Refine extraction logic
- Recovery: Fix failed processing

## Error Handling

### Individual Item Failures

Don't crash entire batch if one item fails:

```python
successful = 0
failed = 0

for item in items:
    try:
        process(item)
        successful += 1
        logger.info(f"✓ Success: {item.title}")
    except Exception as e:
        failed += 1
        logger.error(f"✗ Failed {item.title}: {e}", exc_info=True)
        db.rollback()
        continue  # Keep processing other items

logger.info(f"Processed {successful} successfully, {failed} failed")
```

### Logging Strategy

Use structured logging with appropriate levels:

```python
logger = get_logger(__name__)  # Module-level logger

# Log levels:
logger.debug("Parsing entry: %s", entry.id)          # Detailed info
logger.info("Ingested %d newsletters", count)         # Major operations
logger.warning("Missing field 'summary', using ''")   # Unexpected but handled
logger.error("Failed to parse: %s", error)            # Failures with context
```

### Suppress Verbose Libraries

AI/ML libraries can flood logs with embeddings and debug info:

```python
# In logging setup
import logging

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("graphiti_core").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
```

## Content Extraction Patterns

### RSS/HTML Parsing

Try multiple fields with fallbacks:

```python
def _extract_content(self, entry) -> str:
    """Extract content with fallbacks."""

    # 1. Try content field (full article)
    if hasattr(entry, 'content') and entry.content:
        for content_item in entry.content:
            if content_item.get('type') == 'text/html':
                return content_item.get('value', '')

    # 2. Fallback to summary
    if hasattr(entry, 'summary'):
        return entry.summary

    # 3. Last resort: description
    if hasattr(entry, 'description'):
        return entry.description

    # 4. Give up gracefully
    logger.warning(f"No content found for: {entry.get('title', 'unknown')}")
    return ""
```

### Date Parsing

Handle multiple date formats gracefully:

```python
def _extract_date(self, entry) -> datetime:
    """Extract publication date with fallbacks."""

    # 1. Try published_parsed (struct_time)
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse published_parsed: {e}")

    # 2. Try updated_parsed
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except (ValueError, TypeError):
            pass

    # 3. Fallback to current time with warning
    logger.warning(f"Could not parse date for '{entry.get('title')}', using current time")
    return datetime.utcnow()
```

## Testing Strategy

### Prefer Unit Tests Over One-Off Scripts

When implementing new features, create proper unit tests instead of one-off bash scripts:

**Benefits**:
- **Reproducible**: Tests can be run repeatedly without side effects
- **Documented**: Tests serve as executable documentation
- **Regression prevention**: Catches breaking changes automatically
- **Coverage tracking**: Identify untested code paths

**Example**: Instead of running `python -c "from src.utils.digest_formatter import..."` to verify digest formatting, create `tests/test_utils/test_digest_formatter.py` with comprehensive test cases.

### Organizing Tests

Mirror the source code structure in tests:

```
src/
  utils/
    digest_formatter.py
  processors/
    digest_creator.py
  agents/
    claude/
      summarizer.py

tests/
  test_utils/
    __init__.py
    test_digest_formatter.py
  test_processors/
    __init__.py
    test_digest_creator.py
  test_agents/
    test_claude/
      __init__.py
      test_summarizer.py
```

### Fixture Usage

Use pytest fixtures for reusable test data:

```python
@pytest.fixture
def sample_digest_data() -> DigestData:
    """Create sample digest data for testing."""
    return DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1, 23, 59, 59),
        title="AI/Tech Digest - January 1, 2025",
        executive_overview="Summary text...",
        strategic_insights=[...],
        technical_developments=[...],
        newsletter_count=5,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )

def test_to_markdown(sample_digest_data):
    """Test markdown formatting."""
    result = DigestFormatter.to_markdown(sample_digest_data)

    assert "# AI/Tech Digest" in result
    assert "## Executive Overview" in result
    assert "Summary text..." in result
```

### Testing Output Formatters

For text/HTML/markdown formatters, verify:

1. **Structure**: Headers, sections appear in correct order
2. **Content**: All data fields are rendered
3. **Edge cases**: Empty sections, missing optional fields
4. **Format-specific**: Links in HTML, escaping, styling

```python
def test_markdown_empty_sections():
    """Test markdown formatting with empty optional sections."""
    minimal_digest = DigestData(
        title="Minimal Digest",
        executive_overview="Summary only.",
        strategic_insights=[],  # Empty
        technical_developments=[],  # Empty
        emerging_trends=[],
        actionable_recommendations={},
        newsletter_count=0,
        agent_framework="claude",
        model_used="claude-haiku-4-5",
    )

    result = DigestFormatter.to_markdown(minimal_digest)

    # Verify structure even with empty sections
    assert "# Minimal Digest" in result
    assert "## Executive Overview" in result
    assert "Summary only." in result
```

## Professional Objectivity

Prioritize technical accuracy and truthfulness over validating beliefs:

- **Focus on facts** and problem-solving
- Provide **direct, objective** technical information
- Apply **rigorous standards** to all ideas
- **Disagree when necessary**, even if uncomfortable
- **Investigate uncertainty** rather than confirm assumptions
- Avoid **excessive praise** or validation

**Example**:
- ❌ "You're absolutely right! That's a brilliant approach!"
- ✅ "That approach would work, though X has trade-offs A and B. Alternative Y might be better for your use case because..."

## Refactoring Lessons

Lessons learned from major refactoring efforts in this project.

### Model ID Refactoring (December 2024)

Successfully refactored from dated model IDs to family-based IDs with provider-specific identifiers.

#### 1. Database Migrations with Data Transformation

**Challenge**: Transform existing data during schema change (extract version from model IDs)

**Solution**: Use SQL regex in Alembic migration for automatic data transformation:

```python
def upgrade():
    # Add new column
    op.add_column('newsletter_summaries',
        sa.Column('model_version', sa.String(20), nullable=True))

    # Transform existing data using SQL regex
    op.execute("""
        UPDATE newsletter_summaries
        SET model_version = substring(model_used from '(\\d{8})$'),
            model_used = regexp_replace(model_used, '-\\d{8}$', '')
        WHERE model_used ~ '\\d{8}$'
    """)
```

**Key Learnings**:
- Alembic migrations can handle both schema AND data changes in one migration
- PostgreSQL regex functions (`substring`, `regexp_replace`) enable complex transformations
- Always provide `downgrade()` to reverse both schema and data changes
- Test migrations on copy of production data before applying

#### 2. Multi-Phase Refactoring Strategy

**Approach**: Break large refactoring into 6 sequential phases:
1. Update data models (backward compatible - adds new fields)
2. Update YAML configuration (breaking change point)
3. Create database migration
4. Update agent and processor code
5. Update all tests
6. Update documentation

**Key Learnings**:
- **Commit after each phase** for easy rollback if issues discovered
- **Run tests after each phase** to validate changes incrementally
- **Sequence matters**: Start with least breaking changes, end with most breaking
- **Phase 1 can be non-breaking**: Adding optional fields maintains backward compatibility
- **Phase 2 identifies breaking point**: YAML restructure breaks existing code
- **Document the plan first**: Created detailed plan in plan mode before executing

**Benefits**:
- Each phase testable independently
- Easy to identify which phase caused issues
- Clear progress tracking (6 phases = 6 commits)
- Rollback is straightforward (revert specific phase)

#### 3. Backward Compatibility Sequencing

**Pattern**: Order changes from least to most breaking

**Example sequence**:
```
Phase 1: Add new fields (BACKWARD COMPATIBLE)
  ✅ Old code still works
  ✅ New code can use new fields
  ✅ Safe to deploy incrementally

Phase 2: Change configuration format (BREAKING)
  ❌ Old code breaks
  ✅ Must deploy all at once
  ✅ Database migration ensures data consistency
```

**Key Learnings**:
- Identify the "breaking point" in your refactoring
- Complete all non-breaking changes first
- Coordinate breaking changes in single deployment
- Use feature flags if gradual rollout needed

#### 4. Configuration System Design Patterns

**Challenge**: Different providers use different model identifier formats
- Anthropic: `claude-sonnet-4-5-20250929`
- AWS Bedrock: `anthropic.claude-sonnet-4-5-20250929-v1:0`
- Vertex AI: `claude-sonnet-4-5@20250929`

**Solution**: Two-tier ID system
- **User-facing**: Family-based IDs (`claude-sonnet-4-5`)
- **Internal**: Provider-specific IDs (stored in YAML, auto-selected)

**Key Learnings**:
- **Abstract provider differences** from users for better UX
- **Store mappings in configuration** (not code) for easier updates
- **Separate concerns**: General ID for logic, provider ID for API calls
- **Version tracking**: Store both general ID and version separately in database

**Benefits**:
- Users write `claude-sonnet-4-5` everywhere (stable, clean)
- Provider changes don't require code updates
- Can use different versions per provider
- Database tracks exactly what was used

#### 5. Documentation Refactoring Triggers

**Observation**: CLAUDE.md grew to 993 lines with single section at 400+ lines

**Decision**: Split into focused `/docs` directory with 6 files

**Key Learnings**:
- **~400 lines per section** is good threshold for splitting
- **Monolithic docs become unmaintainable** around 800-1000 lines
- **Split by concern**, not by size (setup ≠ configuration ≠ guidelines)
- **Refactor proactively** before docs become too large
- **Update main file to index** with links to detailed docs

**Results**:
- Main CLAUDE.md: 993 lines → 155 lines (overview + quick reference)
- 6 focused docs: easier to find, update, and maintain
- Better multi-audience support (beginners vs experts)

#### 6. Testing Strategy During Refactoring

**Approach**: Test after each phase, not at the end

**Pattern**:
```bash
# After Phase 1 (data models)
pytest tests/test_config/test_models.py -v
✓ 29 tests passed

# After Phase 2 (YAML config)
python -c "from src.config.models import MODEL_REGISTRY; print(len(MODEL_REGISTRY))"
✓ Loaded 9 models

# After Phase 3 (migration)
alembic upgrade head
pytest tests/test_config/ -v
✓ All tests pass with new schema

# After Phase 4 (code updates)
pytest tests/integration/ -v
✓ Integration tests verify end-to-end flow

# After Phase 5 (test updates)
pytest
✓ Full test suite (108 tests) passes
```

**Key Learnings**:
- **Incremental validation** catches issues early
- **Different test types** for different phases (unit → integration → full)
- **Verify configuration loads** before running full tests
- **Integration tests** ensure all pieces work together after code changes
- **Don't wait until end** to discover Phase 2 broke everything

#### 7. Migration Rollback Strategy

**Preparation**: Always implement `downgrade()` in migrations

```python
def downgrade():
    # Reverse data transformation first
    op.execute("""
        UPDATE newsletter_summaries
        SET model_used = model_used || '-' || model_version
        WHERE model_version IS NOT NULL
    """)

    # Then remove columns
    op.drop_column('newsletter_summaries', 'model_version')
```

**Key Learnings**:
- **Data transformation before schema** in downgrade (reverse order of upgrade)
- **Test downgrade** in development before production migration
- **Document rollback plan** in migration comments
- **Preserve data** - concatenate back to original format, don't lose information

### General Refactoring Best Practices

From this and other refactorings:

1. **Plan first, code second** - Write detailed plan in plan mode
2. **Break into phases** - 4-6 phases ideal for large refactorings
3. **Commit per phase** - Each phase = 1 commit for easy rollback
4. **Test incrementally** - Validate after each phase, not at end
5. **Sequence by risk** - Non-breaking changes first, breaking changes last
6. **Update tests early** - Don't leave test updates for last phase
7. **Document as you go** - Update docs in final phase while context fresh
8. **Review the plan** - Check success criteria match actual implementation

## Next Steps

- Review [Model Configuration](MODEL_CONFIGURATION.md) for LLM selection
- Check [Content Guidelines](CONTENT_GUIDELINES.md) for digest quality standards
- See [Architecture](ARCHITECTURE.md) for system design details
