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

All ingestion uses the unified Content model.

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
- On-demand content fetching via LLM tools
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

### Audio Digests

Generate single-voice narration from approved digests:

```bash
# Via API (recommended - uses background tasks):
# Generate audio digest for digest #42
curl -X POST "http://localhost:8000/api/v1/digests/42/audio" \
  -H "Content-Type: application/json" \
  -d '{"voice": "nova", "speed": 1.0}'

# List all audio digests
curl "http://localhost:8000/api/v1/audio-digests/"

# Get statistics
curl "http://localhost:8000/api/v1/audio-digests/statistics"

# Stream audio file
curl "http://localhost:8000/api/v1/audio-digests/1/stream" -o digest.mp3
```

**Available Voices (OpenAI TTS):**
- `nova` (default) - Warm female voice
- `onyx` - Deep male voice
- `echo` - Natural male voice
- `shimmer` - Expressive female voice
- `alloy` - Neutral voice
- `fable` - Storytelling voice

**TTS Character Limits:**
- OpenAI: 4,096 characters per chunk
- ElevenLabs: 5,000 characters per chunk
- Long digests are automatically split and concatenated

See [Review System Documentation](REVIEW_SYSTEM.md#audio-digests) for full API reference.

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
# - GET  /api/v1/audio-digests/   - List audio digests
# - POST /api/v1/digests/{id}/audio - Generate audio digest
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
- Returns: `ContentData` (Pydantic model)
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
content_items = client.fetch_feed(url)

# Service - business logic + persistence
service = RSSContentIngestionService()
count = service.ingest_content(feed_urls)
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
    content = db.query(Content).first()
    content.status = ProcessingStatus.PROCESSING
    db.commit()  # Object expires here!

    # This would raise DetachedInstanceError:
    print(content.title)  # ERROR!
```

```python
# WITH expire_on_commit=False, this works:
with get_db() as db:
    content = db.query(Content).first()
    content.status = ProcessingStatus.PROCESSING
    db.commit()  # Object remains usable

    print(content.title)  # Works!
```

**Best Practices:**

1. **Don't add per-session workarounds**: Never use `db.expire_on_commit = False` in individual code blocks - the global setting handles this.

2. **Use eager loading for relationships**: When returning objects that will be used after session closes, use `joinedload()` or `selectinload()` for any relationships you need:

```python
from sqlalchemy.orm import joinedload

# Load content relationship when querying summaries
summaries = (
    db.query(Summary)
    .options(joinedload(Summary.content))
    .all()
)

# Now summary.content works even after session closes
for summary in summaries:
    print(summary.content.title)  # Works!
```

3. **Convert to dicts for API responses**: When returning data through APIs, convert ORM objects to dictionaries/Pydantic models within the session:

```python
with get_db() as db:
    contents = db.query(Content).all()

    # Convert to dicts inside session - safe pattern
    return [
        {
            "id": c.id,
            "title": c.title,
            "published_date": c.published_date,
        }
        for c in contents
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
| `summary.content.title` after session close | Lazy-loaded relationship fails | Use `joinedload()` |
| Accessing object after `db.commit()` | Object would be expired | Global `expire_on_commit=False` |
| Returning ORM objects from functions | Detached from session | Convert to dict/Pydantic |
| Adding `db.expire_on_commit = False` inline | Inconsistent, clutters code | Use global setting |

### Deduplication

Always check for existing records before inserting:

```python
existing = db.query(Content).filter(
    Content.source_id == content_data.source_id
).first()

if existing:
    if force_reprocess:
        # Update and reset status for reprocessing
        existing.status = ProcessingStatus.PENDING
        existing.markdown_content = content_data.markdown_content
        existing.raw_content = content_data.raw_content
        db.commit()
        logger.info(f"Reset for reprocessing: {existing.title}")
    else:
        logger.debug(f"Already exists: {existing.title}")
        continue  # Skip, already exists
else:
    # Create new record
    content = Content(**content_data.dict())
    db.add(content)
```

### Session Management

Use context managers for proper cleanup:

```python
with get_db() as db:
    # Database operations
    content = Content(...)
    db.add(content)
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
@click.option('--force', is_flag=True, help='Force reprocess existing content')
def ingest(force: bool):
    service = GmailContentIngestionService(force_reprocess=force)
    count = service.ingest_content()
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
logger.info("Ingested %d content items", count)       # Major operations
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
        content_count=5,
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

### Database Provider Testing

Database providers have a two-tier testing strategy:

**Tier 1: Unit Tests (Mocked)**
- Location: `tests/test_storage/`
- Run with: `pytest tests/test_storage/ -v`
- Uses mock transports to simulate API responses
- Tests edge cases, error handling, retries
- Fast (~1 second), works offline

```python
# Example: Mocking Neon API responses
def create_mock_transport(responses):
    def handler(request):
        for (method, pattern), data in responses.items():
            if method == request.method and pattern in str(request.url):
                return httpx.Response(data["status_code"], json=data["json"])
        return httpx.Response(404)
    return httpx.MockTransport(handler)
```

**Tier 2: Integration Tests (Real APIs)**
- Location: `tests/integration/`
- Run with: `pytest tests/integration/ -v`
- Creates real resources (e.g., Neon branches, Supabase connections)
- Verifies actual API behavior, SSL, connection handling
- Auto-skips when credentials not configured

```python
# Neon integration tests use @requires_neon decorator
@requires_neon
@pytest.mark.asyncio
class TestNeonDatabaseOperations:
    async def test_execute_sql_on_branch(self, neon_test_branch):
        # neon_test_branch creates a real ephemeral branch
        engine = create_async_engine(convert_to_asyncpg_url(neon_test_branch))
        # ... test real database operations

# Supabase integration tests use @requires_supabase decorator
@requires_supabase
class TestSupabaseConnection:
    def test_pooled_connection_works(self, supabase_engine):
        # supabase_engine connects to real Supabase instance
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
```

**Test coverage by provider:**

| Provider | Unit Tests | Integration Tests | Fixtures |
|----------|------------|-------------------|----------|
| Local | `test_providers.py` | `conftest.py` | `test_db_engine`, `db_session` |
| Neon | `test_neon_branch.py` | `test_neon_integration.py` | `neon_test_branch`, `neon_manager` |
| Supabase | `test_providers.py` | `test_supabase_provider.py` | `supabase_engine`, `supabase_direct_engine` |

**Key insight**: Unit tests catch logic errors fast; integration tests catch API compatibility issues. Both are necessary for reliable database providers.

**Session-scoped fixtures for cloud providers**: Cloud provider fixtures use `scope="session"` to create connections once per test session, avoiding repeated connection overhead while still cleaning up properly:

```python
@pytest.fixture(scope="session")
def supabase_engine(supabase_provider):
    if supabase_provider is None:
        pytest.skip("Supabase not configured")
    engine = create_engine(
        supabase_provider.get_engine_url(),
        **supabase_provider.get_engine_options(),
    )
    yield engine
    engine.dispose()  # Clean up at session end
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
        content_count=0,
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

## Case Studies & Lessons Learned

For detailed documentation of major refactoring efforts and lessons learned, see **[Case Studies](CASE_STUDIES.md)**.

Topics covered:
- Model ID Refactoring (December 2024) - Multi-phase migration strategy
- Newsletter → Content Migration (January 2025) - FK migration patterns
- Multi-Provider LLM Routing (January 2025) - Provider abstraction
- General Refactoring Best Practices

## Next Steps

- Review [Model Configuration](MODEL_CONFIGURATION.md) for LLM selection
- Check [Content Guidelines](CONTENT_GUIDELINES.md) for digest quality standards
- See [Architecture](ARCHITECTURE.md) for system design details
- Read [Review System](REVIEW_SYSTEM.md) for digest review and revision workflow
