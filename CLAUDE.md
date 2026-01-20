<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

Comprehensive documentation is available in the `/docs` directory:

- **[Overview & Quick Start](docs/README.md)** - Project introduction and getting started
- **[Setup Guide](docs/SETUP.md)** - Development environment setup and configuration
- **[Architecture](docs/ARCHITECTURE.md)** - System design, tech stack, and workflows
- **[Markdown Pipeline](docs/MARKDOWN_PIPELINE_DESIGN.md)** - End-to-end markdown flow from ingestion to rendering
- **[Model Configuration](docs/MODEL_CONFIGURATION.md)** - LLM selection, providers, and cost optimization
- **[Content Guidelines](docs/CONTENT_GUIDELINES.md)** - Digest quality standards and formatting
- **[Development Guide](docs/DEVELOPMENT.md)** - Commands, patterns, and best practices

- Always use Context7 MCP when you need library/API documentation, code generation, setup or configuration steps for external libraries without me having to explicitly ask.


## Quick Reference

### Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers at Comcast stay informed on AI/Data trends
- **Voice**: Strategic leadership spanning CTO-level strategy to individual practitioner best practices
- **Sources**: Gmail newsletters, Substack RSS feeds, YouTube playlists
- **Output**: Structured digests with knowledge graph-powered historical context

### Key Commands

```bash
# Setup
source .venv/bin/activate
docker compose up -d
alembic upgrade head

# Development servers (frontend + backend)
make dev-bg        # Start in background
make dev-logs      # View logs
make dev-stop      # Stop servers

# Content Ingestion (uses unified Content model)
python -m src.ingestion.gmail          # Gmail newsletters
python -m src.ingestion.substack       # RSS feeds
python -m src.ingestion.youtube        # YouTube playlists

# Processing
python -m src.processors.summarizer    # Summarize pending content
python -m src.processors.digest_creator --type daily

# Testing
pytest
pytest tests/test_config/test_models.py -v

# API (or use make dev-bg)
uvicorn src.api.app:app --reload
```

See [Development Guide](docs/DEVELOPMENT.md#development-commands) for complete command reference.

### Model Configuration

Configure models per pipeline step using **family-based IDs**:

```bash
# Environment variables (.env)
MODEL_SUMMARIZATION=claude-haiku-4-5       # Fast, cost-effective
MODEL_THEME_ANALYSIS=claude-sonnet-4-5     # Quality reasoning
MODEL_DIGEST_CREATION=claude-sonnet-4-5    # Customer-facing
MODEL_HISTORICAL_CONTEXT=claude-haiku-4-5  # Simple queries
```

See [Model Configuration](docs/MODEL_CONFIGURATION.md) for detailed options, cost optimization, and provider setup.

### Pipeline Steps

| Step | Purpose | Default Model |
|------|---------|---------------|
| **SUMMARIZATION** | Extract key points from newsletters | Claude Haiku |
| **THEME_ANALYSIS** | Identify patterns across summaries | Claude Sonnet |
| **DIGEST_CREATION** | Generate multi-audience output | Claude Sonnet |
| **HISTORICAL_CONTEXT** | Query knowledge graph | Claude Haiku |

### Architecture Overview

```
src/
  agents/           # Multi-framework agents (Claude, OpenAI, Google, Microsoft)
  ingestion/        # Content fetching (Gmail, RSS, YouTube)
  processors/       # Core processing (summarize, analyze, create digests)
  storage/          # PostgreSQL + Graphiti/Neo4j
  config/           # Model registry and configuration
  delivery/         # Email and web output
  api/              # FastAPI endpoints (/contents, /summaries, /digests)
```

See [Architecture](docs/ARCHITECTURE.md) for complete system design.

## Development Guidelines

### Git Workflow
- **Commit frequently**: After each major feature/task
- **Descriptive messages**: Explain the "why", not just "what"
- **Test before commit**: Run relevant tests

### Feature Planning
- **Use plan mode**: For significant features, create implementation plans before coding
- **Archive plans**: Move completed plans from `.claude/plans/` to `docs/plans/` after PR merge
- **Reference in PRs**: Link to the archived plan in PR descriptions

### Code Quality
- **Run tests**: `pytest` before committing
- **Type checking**: `mypy src/`
- **Linting**: `ruff check src/`
- **Prefer Edit tool over sed**: Safer, more precise

### SQLAlchemy and Mypy
- **Use SQLAlchemy 2.0's built-in mypy plugin**: Don't install `sqlalchemy-stubs` - it conflicts with SQLAlchemy 2.0
- **Configure overrides for ORM modules**: SQLAlchemy Column types need `disable_error_code` for `assignment`, `arg-type`, `union-attr` etc.
- **Pre-commit hooks**: All mypy dependencies (including SQLAlchemy) must be in `additional_dependencies`
- **Type ignore comments**: Use specific error codes like `# type: ignore[no-any-return]` not generic `# type: ignore`
- **Optional in lists**: When passing `str | None` to functions expecting `list[str]`, guard against None:
  ```python
  # Wrong - mypy error: List item has incompatible type "str | None"
  func([obj.field])  # where field is str | None

  # Correct - guard against None
  if obj.field:
      func([obj.field])
  ```

### Document Parsing
- **Parser abstraction**: Use `DocumentParser` interface in `src/parsers/base.py` for all document parsing
- **Markdown-centric**: All parsers output markdown via `DocumentContent` model - optimized for LLM consumption
- **ClassVar for class attributes**: Mutable class attributes (like `supported_formats`) must use `ClassVar[set[str]]` to satisfy ruff RUF012
- **Union syntax in isinstance**: Use `isinstance(x, bytes | BinaryIO)` not `isinstance(x, (bytes, BinaryIO))` for Python 3.10+ (UP038)
- **MarkItDown for lightweight parsing**: Office docs, HTML, audio
- **DoclingParser for advanced PDFs**: Complex layouts, table extraction, OCR support via `docling>=2.60.0`
- **YouTubeParser for transcripts**: Direct youtube-transcript-api usage for timestamp preservation and deep-linking
- **ParserRouter**: Routes documents to appropriate parser based on format detection with fallback support
- **Lazy converter loading**: DoclingParser uses lazy `converter` property to defer heavy import until first use
- **Type ignore for untyped libraries**: Use `# type: ignore[attr-defined]` for libraries without type stubs (e.g., youtube-transcript-api)
- **TYPE_CHECKING imports**: Use `if TYPE_CHECKING:` block for Docling types to avoid import errors when docling not installed

### HTML-to-Markdown Conversion
- **HtmlMarkdownConverter**: Use `src/parsers/html_markdown.py` for web content extraction during ingestion
- **Trafilatura-based**: Primary extraction uses Trafilatura (~50ms) for academic-quality markdown output
- **Dual input modes**: Pass `url=` for RSS feeds (fetches and extracts), `html=` for Gmail (raw HTML)
- **Async-native**: Use `await converter.convert()` in async contexts; sync wrapper `convert_html_to_markdown()` available for legacy code
- **Quality validation**: `validate_markdown_quality()` checks length, structure, and code block integrity
- **Batch processing**: `batch_convert()` processes multiple items concurrently with semaphore limiting
- **Crawl4AI fallback**: Optional JS-rendering fallback (disabled by default, enable with `use_crawl4ai_fallback=True`)
- **Type casting for untyped returns**: Trafilatura returns `Any`; use explicit `str(result) if result else None` to satisfy mypy
  ```python
  # Usage examples
  converter = HtmlMarkdownConverter()

  # From URL (RSS feeds)
  result = await converter.convert(url="https://example.com/article")

  # From raw HTML (Gmail)
  result = await converter.convert(html="<html>...</html>")

  # Sync wrapper for legacy code
  from src.parsers.html_markdown import convert_html_to_markdown
  markdown = convert_html_to_markdown(html=email_body)
  ```

### Unified Content Model
- **⚠️ Newsletter model is deprecated**: Use `Content` model for all new code. The Newsletter model, its TypeScript types, and `/newsletters` route are deprecated and will be removed in a future release.
- **Prefer Content model**: Use `*ContentIngestionService` classes (e.g., `GmailContentIngestionService`, `RSSContentIngestionService`, `YouTubeContentIngestionService`, `FileContentIngestionService`) over legacy `*IngestionService` classes
- **Content-based lookups**: Use `/summaries/by-content/{content_id}` endpoint for content-to-summary navigation
- **Source types**: `ContentSource` enum defines: `GMAIL`, `RSS`, `YOUTUBE`, `FILE_UPLOAD`
- **Frontend ingestion**: Content page has Ingest button with dialog for Gmail/RSS/YouTube sources
- **Dashboard stats**: Use `useContentStats()` hook, not `useNewsletterStats()`

### Content-Based Summarization
- **Summarization endpoint**: Use `/api/v1/contents/summarize` (not `/summaries/generate`)
- **Summary routes use content_id only**: All summary list/detail endpoints require `content_id`, legacy `newsletter_id` summaries are excluded
- **SSE progress tracking**: Summarization returns a `task_id`, track progress via `/contents/summarize/status/{task_id}` SSE endpoint
- **Retry failed items**: Pass `retry_failed: true` to reset failed content to PARSED status and re-attempt
- **Race condition handling**: Summarizer catches `UniqueViolation` when concurrent processes create same summary - treats as success
- **Status sync**: Content status may get out of sync with summary existence. Fix with:
  ```python
  # Update content status for items that have summaries but aren't COMPLETED
  db.query(Content).filter(
      Content.id.in_(content_ids_with_summaries),
      Content.status != ContentStatus.COMPLETED
  ).update({Content.status: ContentStatus.COMPLETED})
  ```
- **Frontend types**: `SummaryListItem` uses `content_id`, `title`, `publication` (no `newsletter_id`)
- **Navigation**: Summary list links use `/review/summary/$id` with `search={{ source: "content" }}`

### File Upload Ingestion
- **FileContentIngestionService**: Processes file uploads via `ParserRouter`, stores as Content records
- **Deduplication**: SHA-256 file hash for duplicate detection, links duplicates to canonical record
- **API endpoint**: `POST /api/v1/documents/upload` accepts multipart form data
- **Size limits**: Configure via `MAX_UPLOAD_SIZE_MB` and `DOCLING_MAX_FILE_SIZE_MB` settings
- **Format validation**: Router provides `get_supported_formats()` to check available formats

### YouTube Ingestion
- **YouTubeClient**: Handles YouTube Data API authentication (OAuth for private, API key for public playlists)
- **YouTubeContentIngestionService**: Processes playlists and stores transcripts as Content entries (prefer over deprecated `YouTubeIngestionService`)
- **CLI entry point**: `python -m src.ingestion.youtube` with `--playlist-id`, `--public-only`, `--after-date` options
- **Playlist config file**: `youtube_playlists.txt` with `PLAYLIST_ID | description` format
- **API key fallback**: `settings.get_youtube_api_key()` returns YOUTUBE_API_KEY or falls back to GOOGLE_API_KEY
- **datetime.UTC**: Use `datetime.UTC` instead of `timezone.utc` for Python 3.11+ (ruff UP017)
- **Mypy overrides**: Add modules to `[[tool.mypy.overrides]]` in pyproject.toml for dynamic attribute patterns

### YouTube Keyframe Extraction (Optional)
- **KeyframeExtractor**: Uses ffmpeg scene detection to extract slide frames from videos
- **Perceptual hashing**: imagehash library for deduplicating similar slides
- **Opt-in feature**: Enable via `YOUTUBE_KEYFRAME_EXTRACTION=true`
- **Dependencies**: ffmpeg (system), yt-dlp, imagehash, Pillow (Python)
- **noqa comments for security**: Use `# noqa: S108` for temp paths, `# noqa: S607` for subprocess with partial paths

### RSS Ingestion
- **RSSContentIngestionService**: Preferred service for RSS feed ingestion using unified Content model
- **Timezone-aware datetimes**: feedparser's `published_parsed` returns UTC time but as naive struct_time - always add `tzinfo=UTC` when converting:
  ```python
  datetime(*entry.published_parsed[:6], tzinfo=UTC)  # Correct
  datetime(*entry.published_parsed[:6])  # Wrong - causes comparison errors
  ```
- **Date comparison errors**: `TypeError: can't compare offset-naive and offset-aware datetimes` means one datetime has timezone info and the other doesn't - make both UTC-aware
- **Feed URL maintenance**: Check `substack_feeds.txt` periodically - feeds may become unavailable (404) or move (301)

### Async/Await Patterns
- **asyncio.to_thread() with kwargs**: When calling sync functions with keyword arguments in async context, wrap in a lambda:
  ```python
  # Wrong - to_thread doesn't accept keyword arguments directly
  await asyncio.to_thread(sync_func, kwarg=value)

  # Correct - wrap in lambda
  await asyncio.to_thread(lambda: sync_func(kwarg=value))
  ```
- **Background tasks**: Use FastAPI's `BackgroundTasks` for fire-and-forget operations
- **SSE for progress**: Use `StreamingResponse` with `text/event-stream` for real-time progress updates

### Tool Usage Best Practices
- **Always activate venv**: `source .venv/bin/activate` before running scripts
- **Use fixtures**: Reusable test data with pytest fixtures
- **Error handling**: Don't crash entire batch if one item fails

### Utility Functions and Data Models
- **Handle both dict and Pydantic models**: Utility functions that process data from JSON columns may receive either dicts (from raw JSON) or Pydantic model objects (from ORM relationships). Use a helper function pattern:
  ```python
  def _get_attr(obj: dict[str, Any] | PydanticModel, key: str) -> Any:
      if isinstance(obj, dict):
          return obj.get(key)
      return getattr(obj, key, None)
  ```
- **TYPE_CHECKING imports**: Use `if TYPE_CHECKING:` for Pydantic model imports in utility modules to avoid circular imports
- **Type annotations with quotes**: When using TYPE_CHECKING imports, quote the type annotations: `def foo(data: "dict | MyModel") -> str:`
- **Test migrations on production copy**: Always run `--dry-run` first to catch type mismatches before actual migration

See [Development Guide](docs/DEVELOPMENT.md#development-guidelines) for detailed best practices.

## Learning Goals

This project serves as a **comparison framework for agent development kits**:
- Document developer experience for each framework
- Compare API design, tool use, orchestration patterns
- Benchmark performance (speed, quality, token usage)
- Analyze cost implications
- Identify strengths/weaknesses for different use cases

## Environment Configuration

Minimum required in `.env`:

```bash
# Databases
DATABASE_URL=postgresql://localhost/newsletters
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687

# LLM API (minimum: Anthropic for Claude SDK)
ANTHROPIC_API_KEY=sk-ant-...

# Environment
ENVIRONMENT=development
```

See [Setup Guide](docs/SETUP.md#environment-configuration) for complete configuration options.

## Content Standards

Digests follow multi-audience formatting:
- **Executive Summary**: 2-3 sentences for leadership
- **Strategic Insights**: CTO-level implications
- **Technical Deep-Dives**: Developer-focused details
- **Emerging Trends**: New topics with historical context
- **Actionable Recommendations**: Role-specific actions

See [Content Guidelines](docs/CONTENT_GUIDELINES.md) for detailed standards.

## Getting Help

- **Setup issues**: See [Setup Guide](docs/SETUP.md#troubleshooting)
- **Model configuration**: See [Model Configuration](docs/MODEL_CONFIGURATION.md#troubleshooting)
- **Development patterns**: See [Development Guide](docs/DEVELOPMENT.md)
- **Content questions**: See [Content Guidelines](docs/CONTENT_GUIDELINES.md)
