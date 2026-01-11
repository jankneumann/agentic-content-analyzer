# Project Context

## Purpose

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Mission**: Help technical leaders and developers at Comcast stay informed on AI/Data trends
- **Voice**: Strategic leadership spanning CTO-level strategy to individual practitioner best practices
- **Sources**: Gmail, Substack RSS feeds, YouTube playlists, file uploads (PDF, Office docs, etc.)
- **Output**: Structured digests with knowledge graph-powered historical context

## Tech Stack

### Core
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Web Framework**: FastAPI (APIs, web UI)
- **Task Queue**: Celery + Redis (scheduling, async processing)
- **Testing**: pytest + pytest-asyncio
- **Linting**: ruff
- **Type Checking**: mypy

### Databases
- **PostgreSQL + SQLAlchemy**: Structured data (newsletters, summaries, digests)
- **Graphiti + Neo4j**: Knowledge graph (concepts, themes, temporal relationships)

### Agent Frameworks (Multi-Framework Comparison)
- Claude SDK (Anthropic) - Primary
- OpenAI SDK (Agents/Assistants API)
- Google ADK (Agent Development Kit)
- Microsoft Agent Framework (Semantic Kernel or AutoGen)

### Document Parsing
- **MarkItDown**: Lightweight parsing for Office docs, HTML, audio, YouTube
- **Docling**: Advanced PDF processing with OCR, table extraction, layout analysis
- **YouTubeParser**: Direct transcript extraction with timestamp preservation

## Project Conventions

### Code Style
- Modern Python syntax (3.11+): Use `str | None` over `Optional[str]`, `list[str]` over `List[str]`
- Import organization: stdlib → third-party → local (enforced by ruff I rules)
- Line length: 100 characters
- Formatting: ruff format (Black-compatible)
- Type hints required for public functions
- Use specific `# type: ignore[error-code]` over generic `# type: ignore`

### Architecture Patterns

#### Client-Service Pattern (Ingestion)
- **Client Layer**: Fetches/parses data from external sources, returns Pydantic models, no DB
- **Service Layer**: Business logic + database persistence, uses Client for fetching

Example:
```python
# Client - data fetching only
client = SubstackRSSClient()
newsletters = client.fetch_feed(url)

# Service - business logic + persistence
service = SubstackIngestionService()
count = service.ingest_newsletters(feed_urls)
```

#### Parser Abstraction (Documents)
- `DocumentParser` interface in `src/parsers/base.py`
- All parsers output markdown via `DocumentContent` model
- `ParserRouter` routes documents to appropriate parser based on format

#### SQLAlchemy Session Management
- Global `expire_on_commit=False` to prevent DetachedInstanceError
- Use `joinedload()` for relationships accessed after session close
- Convert to dicts/Pydantic models for API responses within session

### Testing Strategy
- Unit tests mirror source structure: `src/utils/` → `tests/test_utils/`
- Use pytest fixtures for reusable test data
- Prefer unit tests over one-off scripts
- Run `pytest` before committing
- Integration tests for end-to-end flows

### Git Workflow
- **Commit frequently**: After each major feature/task
- **Descriptive messages**: Explain the "why", not just "what"
- **Test before commit**: Run relevant tests
- Use imperative mood: "Add feature" not "Added feature"
- Reference issues: "Fixes #123" or "Relates to #456"

### Feature Planning
- Use OpenSpec for significant features, breaking changes, architecture shifts
- Create proposals in `openspec/changes/[change-id]/`
- Get approval before implementation
- Archive completed changes to `openspec/changes/archive/`

## Domain Context

### Content Pipeline

1. **Ingestion**: Fetch from Gmail/Substack/YouTube → Parse content → Store raw
2. **Summarization**: Individual content → Structured summary → Extract entities
3. **Knowledge Graph**: Store entities/relationships in Graphiti (concepts, temporal evolution)
4. **Theme Analysis**: Query Graphiti for common themes, trending topics, historical context
5. **Digest Generation**: Multi-audience formatting (CTO strategy + developer tactics)
6. **Delivery**: Email/web with daily/weekly schedules

### Multi-Audience Output Structure

```markdown
# AI Newsletter Digest - [Date]

## Executive Overview (2-3 paragraphs)
For senior leadership - what matters and why

## Strategic Insights
CTO-level implications and decisions

## Technical Developments
Developer-focused details and implementations

## Emerging Trends
New and noteworthy (with historical context)

## Actionable Recommendations
- For leadership: [Strategic actions]
- For teams: [Tactical implementations]
- For individuals: [Skill development]
```

### Model Configuration

Configure models per pipeline step using family-based IDs:

| Step | Purpose | Default Model |
|------|---------|---------------|
| SUMMARIZATION | Extract key points from content | Claude Haiku |
| THEME_ANALYSIS | Identify patterns across summaries | Claude Sonnet |
| DIGEST_CREATION | Generate multi-audience output | Claude Sonnet |
| HISTORICAL_CONTEXT | Query knowledge graph | Claude Haiku |

## Important Constraints

### Security
- Never hardcode production credentials
- Validate user inputs at system boundaries
- Use subprocess carefully with controlled inputs
- Follow OWASP top 10 guidelines

### Performance
- Async processing for long-running tasks via Celery
- File size limits for document uploads (MAX_UPLOAD_SIZE_MB)
- Lazy loading for heavy dependencies (e.g., Docling converter)
- Timeout configuration for external API calls

### Cost Control
- Configurable model selection per pipeline step
- Use lighter models (Haiku) for simple tasks
- Use heavier models (Sonnet) for quality-critical tasks
- Monitor token usage per digest

### Dependencies
- SQLAlchemy 2.0's built-in mypy plugin (not sqlalchemy-stubs)
- docling as optional dependency (heavy ML models)
- markitdown for lightweight parsing
- youtube-transcript-api for transcript extraction

## External Dependencies

### APIs
- **Anthropic API**: Primary LLM provider (Claude models)
- **Google APIs**: Gmail API (ingestion), YouTube Data API (playlists)
- **Neo4j**: Knowledge graph backend for Graphiti

### Infrastructure (Docker Compose)
- PostgreSQL 15
- Redis 7
- Neo4j 5

### Environment Variables (Minimum)

```bash
# Databases
DATABASE_URL=postgresql://localhost/newsletters
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687

# LLM API
ANTHROPIC_API_KEY=sk-ant-...

# Environment
ENVIRONMENT=development
```

## Project Structure

```
src/
  agents/           # Multi-framework agents (Claude, OpenAI, Google, Microsoft)
  ingestion/        # Content fetching (Gmail, RSS, YouTube, file uploads)
  parsers/          # Document parsing (Docling, MarkItDown, YouTube)
  processors/       # Core processing (summarize, analyze, create digests)
  storage/          # PostgreSQL + Graphiti/Neo4j
  config/           # Model registry and configuration
  delivery/         # Email and web output
  api/              # FastAPI application
```

## Learning Goals

This project serves as a comparison framework for agent development kits:
- Document developer experience for each framework
- Compare API design, tool use, orchestration patterns
- Benchmark performance (speed, quality, token usage)
- Analyze cost implications
- Identify strengths/weaknesses for different use cases
