# Development Guide

## Development Commands

### Quick Start

```bash
# Start frontend and backend in background
make dev-bg

# View logs
make dev-logs

# Stop servers
make dev-stop

# Access points:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### Content Ingestion

All ingestion uses the unified Content model. The legacy Newsletter model is deprecated.

```bash
# Fetch content from Gmail newsletters
python -m src.ingestion.gmail

# Fetch content from Substack RSS feeds
python -m src.ingestion.substack

# Fetch content from YouTube playlists
python -m src.ingestion.youtube

# Force reprocess existing content
python -m src.ingestion.gmail --force
python -m src.ingestion.substack --force
```

### Processing

```bash
# Summarize all pending content (via API)
# Use the web UI at /summaries or call:
curl -X POST http://localhost:8000/api/v1/contents/summarize

# Create a daily digest
python -m src.processors.digest_creator --type daily

# Create a weekly digest
python -m src.processors.digest_creator --type weekly
```

### Review Workflow

```bash
# List all digests pending review
python -m scripts.review_digest --list

# View a specific digest
python -m scripts.review_digest --id 42 --view
python -m scripts.review_digest --id 42 --view --format html

# Quick approve/reject (batch mode)
python -m scripts.review_digest --id 42 --action approve --reviewer "user@example.com"
python -m scripts.review_digest --id 42 --action reject --notes "Too technical" --reviewer "user@example.com"

# Interactive AI-powered revision session
python -m scripts.review_digest --id 42 --revise-interactive --reviewer "user@example.com"

# Generate digest with auto-approval (skip review)
python -m scripts.generate_daily_digest --save --auto-approve
```

**Interactive Revision Session:**
- Multi-turn conversational refinement with AI
- On-demand newsletter content fetching via LLM tools
- Token-efficient context loading (summaries + themes)
- Complete audit trail stored in `revision_history` JSON field
- Cost tracking for revision sessions

**Digest Status Flow:**
```
PENDING → GENERATING → COMPLETED → PENDING_REVIEW
                                        ↓
                        ┌───────────────┼─────────────┐
                        ↓               ↓             ↓
        [Interactive Revision]      APPROVED      REJECTED
                        ↓               ↓
                 PENDING_REVIEW     DELIVERED
```

See [Review System Documentation](REVIEW_SYSTEM.md) for detailed guide.

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
# Recommended: Start both frontend and backend
make dev-bg

# Or start API only
uvicorn src.api.app:app --reload

# API docs available at:
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc

# Key API endpoints:
# - GET  /api/v1/contents         - List content
# - POST /api/v1/contents/ingest  - Trigger ingestion
# - POST /api/v1/contents/summarize - Trigger summarization
# - GET  /api/v1/summaries        - List summaries
# - GET  /api/v1/digests          - List digests
# - GET  /api/v1/scripts          - List podcast scripts
# - GET  /api/v1/podcasts         - List podcasts
#
# All list endpoints support sorting via query parameters:
# - sort_by: Field to sort by (varies by endpoint)
# - sort_order: 'asc' or 'desc' (default: desc)
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

#### Testing Best Practices

**Resilient test database setup**: Session-scoped fixtures should drop tables before creating them to handle interrupted previous runs. Without this, `create_all()` fails on existing tables/indexes:

```python
@pytest.fixture(scope="session")
def test_db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    # Safety check - always include "test" in database name
    if "test" not in engine.url.database.lower():
        raise ValueError("Must use test database")
    # Drop first for clean state (handles interrupted runs)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
```

**Transaction rollback isolation**: Each test gets a fresh session with transaction rollback:

```python
@pytest.fixture
def db_session(test_db_engine):
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

**Sort fallback behavior**: When testing API sort parameters, invalid `sort_by` values fall back to the default field, but `sort_order` is still respected. Don't assume both fall back.

### Linting & Type Checking

```bash
# Lint code with Ruff
ruff check src/ tests/
ruff check src/ tests/ --fix  # Auto-fix issues

# Format code
ruff format src/ tests/

# Type check with mypy
mypy src/

# Run pre-commit hooks manually
pre-commit run --all-files
```

### Pre-Commit Hooks

Pre-commit hooks are configured to run automatically before each commit:

```bash
# Install pre-commit hooks (first time only)
pre-commit install

# Hooks that run on every commit:
# 1. ruff - Linter with auto-fix
# 2. ruff-format - Code formatter
# 3. trailing-whitespace - Remove trailing spaces
# 4. end-of-file-fixer - Ensure newline at EOF
# 5. check-yaml - Validate YAML files
# 6. check-added-large-files - Prevent large file commits
# 7. check-merge-conflict - Detect merge conflict markers
# 8. detect-private-key - Prevent accidental key commits
# 9. mypy - Type checking (optional, can be slow)
```

## Linter Guidelines

This project uses **Ruff** for linting and formatting, configured in `pyproject.toml`.

### Enabled Rule Categories

| Rule | Description | Purpose |
|------|-------------|---------|
| E | pycodestyle errors | Basic Python style errors |
| F | Pyflakes | Undefined names, unused imports |
| I | isort | Import sorting and organization |
| N | pep8-naming | Naming conventions (functions, classes) |
| W | pycodestyle warnings | Style warnings |
| UP | pyupgrade | Modern Python syntax (3.11+) |
| B | flake8-bugbear | Common bugs and design issues |
| C4 | flake8-comprehensions | List/dict comprehension improvements |
| SIM | flake8-simplify | Code simplification suggestions |
| RUF | Ruff-specific | Additional quality rules |
| S | flake8-bandit | Security vulnerability checks |
| ASYNC | flake8-async | Async/await best practices |
| DTZ | flake8-datetimez | Timezone-aware datetime usage |

### Ignored Rules

Some rules are intentionally ignored for project-specific reasons:

```toml
ignore = [
    "E501",   # Line too long - handled by formatter
    "S101",   # Assert in tests - acceptable
    "S105",   # Hardcoded passwords - false positives in tests
    "S106",   # Hardcoded passwords
    "S107",   # Hardcoded default passwords - acceptable for local dev
    "S110",   # try-except-pass - sometimes intentional
    "S603",   # Subprocess call - we control the inputs
    "B008",   # Function call in default argument - FastAPI Depends()
    "B904",   # Raise from err - not critical for HTTPException
    "DTZ001", # datetime.utcnow() - will address separately
    "DTZ003", # datetime.utcnow() - same as above
    "DTZ005", # datetime.now() without tz - will address separately
    "SIM102", # Nested if statements - sometimes more readable
    "SIM105", # contextlib.suppress - try-except-pass is clear
    "SIM108", # Ternary operator - if-else sometimes clearer
    "SIM115", # Context manager for files - sometimes not needed
    "SIM116", # Dict vs if statements - readability preference
    "SIM118", # key in dict vs dict.keys() - minor
    "C401",   # Unnecessary generator - minor
    "C416",   # Unnecessary comprehension - minor
    "N806",   # Variable naming in function - CONSTANTS are fine
    "RUF022", # __all__ sorting - not critical
]
```

### Test-Specific Ignores

Tests have additional relaxed rules to support test patterns:

```toml
"tests/*" = [
    "S101",   # Allow asserts
    "S105",   # Allow test credentials
    "S106",   # Allow test credentials
    "SIM103", # Return condition directly - if-else clearer in tests
    "SIM117", # Nested with statements - more readable in tests
    "F841",   # Unused variables - sometimes needed for setup
    "RUF005", # List concatenation - simpler to read
    "RUF015", # iter() over slice - minor
    "RUF043", # Regex without raw string - acceptable
    "B007",   # Loop variable not used - sometimes intentional
]
```

### Key Linting Principles

1. **Use Modern Python Syntax (UP rules)**:
   ```python
   # Preferred (Python 3.11+)
   def func(arg: str | None = None) -> list[str]:
       ...

   # Avoid (legacy)
   from typing import List, Optional
   def func(arg: Optional[str] = None) -> List[str]:
       ...
   ```

2. **Import Organization (I rules)**:
   ```python
   # Correct order:
   # 1. Standard library
   import os
   from datetime import datetime

   # 2. Third-party
   import pytest
   from anthropic import Anthropic

   # 3. Local (first-party)
   from src.config import settings
   from src.models.digest import Digest
   ```

3. **Security Awareness (S rules)**:
   - Never hardcode production credentials
   - Validate user inputs at system boundaries
   - Use subprocess carefully with controlled inputs

4. **Async Best Practices (ASYNC rules)**:
   - Always await async functions
   - Use `async with` for async context managers
   - Avoid blocking calls in async functions

### Running Linter

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix what can be fixed
ruff check src/ tests/ --fix

# Show all rules and their descriptions
ruff rule --all

# Check specific rule
ruff rule UP045  # Shows details about the rule
```

### Formatting

Ruff's formatter is a drop-in replacement for Black:

```bash
# Check if formatting needed
ruff format src/ tests/ --check

# Apply formatting
ruff format src/ tests/

# Format settings in pyproject.toml
line-length = 100
target-version = "py311"
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

### Feature Planning & Plan Archival

For significant features, use Claude Code's plan mode to create implementation plans before coding. These plans serve as valuable documentation for future reference.

**Planning Workflow**:

1. **Create Plan**: Use plan mode to design the implementation approach
   - Plans are created in `.claude/plans/` during development
   - Include component architecture, API changes, and implementation steps

2. **Archive Plan After PR Merge**: Move completed plans to `docs/plans/` for reference
   ```bash
   # After PR is merged, archive the plan
   mv .claude/plans/feature-name.md docs/plans/YYYY-MM-DD-feature-name.md
   git add docs/plans/
   git commit -m "Archive implementation plan for feature-name"
   ```

3. **Reference Plans in PRs**: Include a link to the plan in the PR description
   ```markdown
   ## Implementation Plan
   See [docs/plans/2025-01-08-revision-chat-panel.md](docs/plans/2025-01-08-revision-chat-panel.md)
   ```

**Plan Naming Convention**:
- Format: `YYYY-MM-DD-feature-name.md`
- Example: `2025-01-08-revision-chat-panel.md`

**What to Include in Archived Plans**:
- Original requirements and goals
- Component architecture decisions
- API design choices
- Implementation steps taken
- Any deviations from the original plan

**Benefits**:
- **Historical context**: Understand why decisions were made
- **Onboarding**: New contributors can learn from past implementations
- **Pattern reference**: Reuse successful approaches for similar features
- **PR documentation**: Clear link between planning and implementation

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

## React/Frontend Patterns

### Component Reset with Key Prop

When a component needs to fully reset its state based on a prop change (like navigating between items in a list), use a `key` prop instead of complex `useEffect` logic.

**Problem**: React doesn't remount components when only props change. Internal state persists.

```tsx
// BUG: When navigating from item 1 to item 2, the chat shows item 1's messages
function ReviewPage({ itemId }) {
  const chat = useChatSession("summary", itemId)  // Hook keeps old state!
  // ...
}
```

**Solution**: Add a `key` prop to force remounting:

```tsx
// CORRECT: Component remounts when itemId changes
<ReviewContent
  key={item.id}  // Forces full remount on navigation
  item={item}
  // ...
/>
```

**When to use `key` for reset**:
- Navigating between detail pages (prev/next buttons)
- Switching between tabs with independent state
- Any time internal hooks need to reinitialize with new props

**Anti-pattern to avoid**:
```tsx
// AVOID: Complex useEffect reset logic
useEffect(() => {
  setMessages([])
  setConversationId(null)
  setIsStreaming(false)
  // ... reset every piece of state
}, [itemId])
```

### Prefer Existing Hooks Over Manual State

Before implementing manual state management, check if existing hooks already handle the use case.

**Example**: The `useChatSession` hook already provided:
- Conversation fetching by artifact
- Automatic conversation loading
- Streaming state management
- Error handling

Instead of manually managing `messages`, `conversationId`, `isStreaming`, etc., use the hook:

```tsx
// BEFORE: 50+ lines of manual state management
const [messages, setMessages] = useState([])
const [conversationId, setConversationId] = useState(null)
const [isStreaming, setIsStreaming] = useState(false)
const [streamingContent, setStreamingContent] = useState("")
const [error, setError] = useState(null)
// ... complex handlers

// AFTER: 3 lines
const chat = useChatSession("summary", summaryId)
// Use: chat.messages, chat.isStreaming, chat.send(), etc.
```

### Merging Local and Persisted State

When you need both persisted state (from API) and local ephemeral state, merge them:

```tsx
// Persisted chat messages from API
const chat = useChatSession("summary", summaryId)

// Local system messages (feedback, confirmations - not persisted)
const [systemMessages, setSystemMessages] = useState([])

// Merge and sort by timestamp for display
const allMessages = useMemo(() => {
  return [...chat.messages, ...systemMessages].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
  )
}, [chat.messages, systemMessages])
```

## Database Patterns

### SQLAlchemy Session Management

**Understanding `expire_on_commit`:**

SQLAlchemy has a default behavior called `expire_on_commit=True` which expires all objects in a session after `commit()` is called. This causes `DetachedInstanceError` when you try to access object attributes after commit or after the session closes.

**Our Solution:**

We configure `expire_on_commit=False` globally in `src/storage/database.py`:

```python
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevents DetachedInstanceError
)
```

**Why This Matters:**

```python
# WITHOUT expire_on_commit=False, this would fail:
with get_db() as db:
    newsletter = db.query(Newsletter).first()
    newsletter.status = ProcessingStatus.PROCESSING
    db.commit()  # Object expires here!

    # This would raise DetachedInstanceError:
    print(newsletter.title)  # ERROR!
```

```python
# WITH expire_on_commit=False, this works:
with get_db() as db:
    newsletter = db.query(Newsletter).first()
    newsletter.status = ProcessingStatus.PROCESSING
    db.commit()  # Object remains usable

    print(newsletter.title)  # Works!
```

**Best Practices:**

1. **Don't add per-session workarounds**: Never use `db.expire_on_commit = False` in individual code blocks - the global setting handles this.

2. **Use eager loading for relationships**: When returning objects that will be used after session closes, use `joinedload()` or `selectinload()` for any relationships you need:

```python
from sqlalchemy.orm import joinedload

# Load newsletter relationship when querying summaries
summaries = (
    db.query(NewsletterSummary)
    .options(joinedload(NewsletterSummary.newsletter))
    .all()
)

# Now summary.newsletter works even after session closes
for summary in summaries:
    print(summary.newsletter.title)  # Works!
```

3. **Convert to dicts for API responses**: When returning data through APIs, convert ORM objects to dictionaries/Pydantic models within the session:

```python
with get_db() as db:
    newsletters = db.query(Newsletter).all()

    # Convert to dicts inside session - safe pattern
    return [
        {
            "id": n.id,
            "title": n.title,
            "published_date": n.published_date,
        }
        for n in newsletters
    ]
```

4. **Use `refresh()` after commit if you need fresh data**: If you need to see database-generated values (like auto-increment IDs or default values):

```python
db.add(new_object)
db.commit()
db.refresh(new_object)  # Load fresh data from DB
return new_object.id  # Now includes DB-generated ID
```

5. **Extract IDs early for nested operations**: When you need IDs for subsequent operations outside the session:

```python
with get_db() as db:
    digest = db.query(Digest).first()
    digest_id = digest.id  # Capture ID while in session
    db.commit()

# Use captured ID outside session
process_digest(digest_id)
```

**Common Pitfalls to Avoid:**

| Pattern | Problem | Solution |
|---------|---------|----------|
| `summary.newsletter.title` after session close | Lazy-loaded relationship fails | Use `joinedload()` |
| Accessing object after `db.commit()` | Object would be expired | Global `expire_on_commit=False` |
| Returning ORM objects from functions | Detached from session | Convert to dict/Pydantic |
| Adding `db.expire_on_commit = False` inline | Inconsistent, clutters code | Use global setting |

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

### SQLAlchemy and Mypy

**Configuration:**
- Use SQLAlchemy 2.0's built-in mypy plugin - don't install `sqlalchemy-stubs` (conflicts with 2.0)
- Configure overrides for ORM modules: SQLAlchemy Column types need `disable_error_code` for `assignment`, `arg-type`, `union-attr`
- Pre-commit hooks: All mypy dependencies (including SQLAlchemy) must be in `additional_dependencies`
- Type ignore comments: Use specific error codes like `# type: ignore[no-any-return]` not generic `# type: ignore`

**Optional in lists:**
```python
# Wrong - mypy error: List item has incompatible type "str | None"
func([obj.field])  # where field is str | None

# Correct - guard against None
if obj.field:
    func([obj.field])
```

### SQLAlchemy Index Definitions

**Avoid duplicate index definitions**: Don't use both `index=True` on a column AND an explicit `Index()` in `__table_args__` with the same name. SQLAlchemy's `index=True` creates an implicit index named `ix_{table}_{column}`:

```python
# WRONG - creates duplicate index 'ix_images_video_id'
video_id = Column(String(20), index=True)  # Creates ix_images_video_id
__table_args__ = (
    Index("ix_images_video_id", "video_id"),  # Conflicts!
)

# CORRECT - use only one method
video_id = Column(String(20))  # No index=True
__table_args__ = (
    Index("ix_images_video_id", "video_id"),  # Explicit index only
)
```

**PostgreSQL enum sorting**: Enums sort by ordinal position (declaration order), not alphabetically. Keep this in mind for ORDER BY queries on enum columns.

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

## Code Patterns

### Async/Await Patterns

**asyncio.to_thread() with kwargs**: When calling sync functions with keyword arguments in async context, wrap in a lambda:

```python
# Wrong - to_thread doesn't accept keyword arguments directly
await asyncio.to_thread(sync_func, kwarg=value)

# Correct - wrap in lambda
await asyncio.to_thread(lambda: sync_func(kwarg=value))
```

**Background tasks**: Use FastAPI's `BackgroundTasks` for fire-and-forget operations.

**SSE for progress**: Use `StreamingResponse` with `text/event-stream` for real-time progress updates.

### Utility Functions and Data Models

**Handle both dict and Pydantic models**: Utility functions that process data from JSON columns may receive either dicts (from raw JSON) or Pydantic model objects (from ORM relationships). Use a helper function pattern:

```python
def _get_attr(obj: dict[str, Any] | PydanticModel, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
```

**TYPE_CHECKING imports**: Use `if TYPE_CHECKING:` for Pydantic model imports in utility modules to avoid circular imports.

**Type annotations with quotes**: When using TYPE_CHECKING imports, quote the type annotations: `def foo(data: "dict | MyModel") -> str:`

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

### Newsletter → Content Migration (January 2025)

Successfully migrated multiple processors from deprecated Newsletter model to unified Content model, eliminating foreign key bugs and standardizing data access patterns.

#### 1. Root Cause Analysis: Deprecated FK References

**Problem**: Processors were querying `newsletter_id` (deprecated FK) instead of `content_id` (new FK) in `NewsletterSummary`, causing empty results when Newsletter records didn't exist.

**Symptom**: Theme analysis and digest creation returned empty summaries despite having valid Content records with summaries.

**Solution**: Systematic audit and update of all FK references:
```python
# Before (broken) - NewsletterSummary.newsletter_id is deprecated
summaries = db.query(NewsletterSummary).filter(
    NewsletterSummary.newsletter_id.in_(newsletter_ids)  # ❌ Wrong FK
).all()

# After (correct) - Use NewsletterSummary.content_id
summaries = db.query(NewsletterSummary).filter(
    NewsletterSummary.content_id.in_(content_ids)  # ✅ Correct FK
).all()
```

**Key Learnings**:
- Deprecation warnings don't prevent bugs - code still compiles and runs
- Search for ALL usages of deprecated FK before considering migration complete
- Use `grep -r "newsletter_id"` to find remaining references

#### 2. Field Naming Changes Between Models

**Challenge**: Newsletter and Content models use different field names for similar data.

**Mapping Table**:
| Newsletter Model | Content Model | Notes |
|------------------|---------------|-------|
| `raw_text` | `markdown_content` | Primary parsed content |
| `raw_html` | `raw_content` | Original unparsed content |
| `source` | `publication` | Origin publication name |
| `newsletter_ids` | `content_ids` | In tool outputs/metadata |
| `newsletter_ids_fetched` | `content_ids_fetched` | In script records |

**Key Learnings**:
- Create a mapping table before starting migration
- Update ALL usages - not just model access but also variable names, API responses, and metadata
- Test output format explicitly (check JSON keys in API responses)

#### 3. LLM Tool Renaming for Agent Processors

**Challenge**: LLM agents have learned tool names - changing them affects prompt effectiveness and requires consistent updates to tool definitions, handlers, and prompts.

**Tool Renames**:
```python
# Tool definitions
"get_newsletter_content" → "get_content"
"fetch_newsletter_content" → "fetch_content"
"search_newsletters" → "search_content"

# Handler dispatch
if tool_name == "get_newsletter_content":  # ❌ Old
if tool_name == "get_content":  # ✅ New

# Prompt instructions
"Use search_newsletters to find..." → "Use search_content to find..."
```

**Key Learnings**:
- Update tool definitions, handler dispatch, AND prompts together
- Tool names in prompts train the LLM - inconsistency confuses the model
- Consider backwards compatibility period for API-exposed tools

#### 4. Eager Loading for Detached Session Access

**Problem**: Accessing relationships after SQLAlchemy session closes raises `DetachedInstanceError`.

**Context**: When loading summaries, we need to access `summary.content` outside the session context.

**Solution**: Use `joinedload()` to eager-load relationships:
```python
from sqlalchemy.orm import joinedload

# Before (fails when accessing summary.content outside session)
summaries = db.query(NewsletterSummary).filter(...).all()

# After (content relationship pre-loaded)
summaries = (
    db.query(NewsletterSummary)
    .options(joinedload(NewsletterSummary.content))  # Eager load
    .filter(...)
    .all()
)

# Now safe to access outside session
for summary in summaries:
    title = summary.content.title  # ✅ Works
```

**Key Learnings**:
- Plan for session lifecycle when designing data access
- Use `joinedload()` for relationships accessed in return values
- Consider using `selectinload()` for one-to-many relationships to avoid N+1

#### 5. Deprecation Warning Strategy

**Approach**: Add warnings to deprecated methods rather than removing them immediately.

```python
import warnings

def get_newsletters(self):
    """Deprecated: Use get_contents() instead."""
    warnings.warn(
        "get_newsletters() is deprecated. Use get_contents() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return self.get_contents()
```

**Key Learnings**:
- Warnings help identify remaining callers during migration
- Keep deprecated methods working (call the new method internally)
- Set `stacklevel=2` so warning shows caller's line, not the deprecated function
- Plan removal date and communicate to team

#### 6. Test Fixture Migration Pattern

**Challenge**: Test fixtures hardcoded Newsletter model assumptions.

**Before**:
```python
@pytest.fixture
def sample_summary():
    return NewsletterSummary(
        newsletter_id=1,  # Deprecated FK
        # ...
    )
```

**After**:
```python
@pytest.fixture
def sample_summary(sample_content):  # Depend on content fixture
    summary = NewsletterSummary(
        content_id=sample_content.id,  # Use content FK
        # ...
    )
    summary.content = sample_content  # Attach for eager-load tests
    return summary
```

**Key Learnings**:
- Update fixtures to use new FKs and attach relationships
- Fixture dependencies should reflect model relationships
- Create content fixtures before summary fixtures
- Explicitly attach relationships for tests that access them

#### 7. Systematic Migration Checklist

Use this checklist for model deprecation migrations:

```markdown
## Pre-Migration
- [ ] Document field name mappings (old → new)
- [ ] Identify all FK references with grep/search
- [ ] List all affected processors/services
- [ ] Create test coverage for affected code paths

## Code Updates
- [ ] Update model FK references
- [ ] Update field name access patterns
- [ ] Rename LLM tool definitions
- [ ] Update LLM tool handlers
- [ ] Update prompt instructions mentioning old names
- [ ] Add eager loading where needed
- [ ] Add deprecation warnings to legacy methods

## Testing
- [ ] Update test fixtures
- [ ] Run affected test modules
- [ ] Test API responses for correct field names
- [ ] Test LLM tool calls end-to-end

## Documentation
- [ ] Update CLAUDE.md guidelines
- [ ] Document lessons learned in DEVELOPMENT.md
- [ ] Update API documentation if applicable
```

### Multi-Provider LLM Routing (January 2025)

Created a unified `LLMRouter` class to abstract LLM provider differences and enable easy provider switching across all pipeline processors.

#### 1. Provider-Agnostic Tool Definitions

**Challenge**: Each LLM provider uses different formats for function/tool calling:
- Anthropic: `input_schema` key, tools list in API call
- Gemini: `FunctionDeclaration` with `parameters` property
- OpenAI: `function` wrapper with `parameters` schema

**Solution**: Create a provider-agnostic `ToolDefinition` dataclass:
```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format

# Usage in processors
PODCAST_TOOLS = [
    ToolDefinition(
        name="get_content",
        description="Retrieve content by ID...",
        parameters={
            "type": "object",
            "properties": {"content_id": {"type": "integer"}},
            "required": ["content_id"],
        },
    ),
]
```

**Key Learnings**:
- Use JSON Schema as the universal parameter format (all providers support it)
- Convert to provider-specific format at the router level, not in processors
- Keep tool definitions with the processors that use them, not in the router

#### 2. Dual Parameterization: Model AND Provider

**Challenge**: Users need control over both model choice AND provider (same model can be served by multiple providers).

**Example**: `claude-sonnet-4-5` available via:
- Anthropic direct API
- AWS Bedrock
- Google Vertex AI

**Solution**: Make provider explicitly configurable with sensible defaults:
```python
class LLMRouter:
    DEFAULT_PROVIDERS = {
        ModelFamily.CLAUDE: Provider.ANTHROPIC,
        ModelFamily.GEMINI: Provider.GOOGLE_AI,
        ModelFamily.GPT: Provider.OPENAI,
    }

    def resolve_provider(
        self,
        model: str,
        provider: Provider | None = None
    ) -> Provider:
        """Return explicit provider or infer from model family."""
        if provider is not None:
            return provider  # Explicit choice honored

        family = ModelRegistry.get_family(model)
        return self.DEFAULT_PROVIDERS.get(family, Provider.ANTHROPIC)
```

**Key Learnings**:
- Don't force users to specify provider if they don't care
- Always allow explicit override for when defaults don't apply
- Provider-specific model IDs should be in configuration, not code

#### 3. API Rate Limit Mitigation Through Provider Switching

**Problem**: Anthropic API returned 529 (Overloaded) and 429 (Rate Limit: 30k tokens/min) errors during script generation.

**Symptoms**:
- Script generation reported "successful but empty"
- Backend logs showed API errors, but generation loop continued
- Default retry logic insufficient for sustained load

**Solution**: Switch to provider with higher rate limits:
```yaml
# model_registry.yaml
defaults:
  # Before: claude-sonnet-4-5 (30k tokens/min on Anthropic)
  podcast_script: gemini-2.5-flash  # Higher rate limits
```

**Key Learnings**:
- Different providers have vastly different rate limits
- Gemini's rate limits are generally higher for equivalent tasks
- Configuration-based model selection enables quick mitigation
- Monitor backend logs for API errors - they may not surface to frontend
- Consider implementing automatic provider fallback for resilience

#### 4. Agentic Loop Abstraction

**Challenge**: Implementing tool-calling loops varies significantly by provider:
- Anthropic: `tool_use` blocks with `tool_use_id`
- Gemini: `function_call` parts requiring `FunctionResponse`
- OpenAI: `tool_calls` with `tool_call_id`

**Solution**: Unified interface hiding provider differences:
```python
async def generate_with_tools(
    self,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[ToolDefinition],
    tool_executor: Callable[[str, dict], Any],
    provider: Provider | None = None,
) -> LLMResponse:
    """Run agentic loop with tool calling until completion."""

    # Router handles:
    # 1. Converting ToolDefinition to provider format
    # 2. Making API calls with correct structure
    # 3. Parsing tool calls from response
    # 4. Formatting tool results for next iteration
    # 5. Detecting completion (no more tool calls)
```

**Key Learnings**:
- Agentic loop structure is similar across providers - abstract it once
- Tool executor callback keeps business logic in processors
- Return structured `LLMResponse` with both content and metadata

#### 5. CSS Overflow Handling in Select Components

**Problem**: Long titles in Select dropdown (dialog context) caused layout overflow - white background didn't resize properly.

**Context**: React dialogs with Radix UI Select components displaying digest/script titles.

**Solution**: Constrain width and truncate text:
```tsx
// Constrain dropdown to dialog width minus padding
<SelectContent className="max-w-[calc(500px-3rem)]">
  {items.map((item) => (
    <SelectItem key={item.id} value={String(item.id)} className="max-w-full">
      {/* Truncate long titles with ellipsis */}
      <span className="truncate">
        [{item.id}] {item.title}
      </span>
    </SelectItem>
  ))}
</SelectContent>
```

**Key Learnings**:
- `max-w-[calc(container - padding)]` constrains dropdown to parent bounds
- `truncate` class adds `text-overflow: ellipsis` and `overflow: hidden`
- Wrap text content in `<span className="truncate">` for reliable truncation
- `max-w-full` on SelectItem ensures it respects parent constraints

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
- Read [Review System](REVIEW_SYSTEM.md) for digest review and revision workflow
