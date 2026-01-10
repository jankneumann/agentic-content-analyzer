# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

Comprehensive documentation is available in the `/docs` directory:

- **[Overview & Quick Start](docs/README.md)** - Project introduction and getting started
- **[Setup Guide](docs/SETUP.md)** - Development environment setup and configuration
- **[Architecture](docs/ARCHITECTURE.md)** - System design, tech stack, and workflows
- **[Model Configuration](docs/MODEL_CONFIGURATION.md)** - LLM selection, providers, and cost optimization
- **[Content Guidelines](docs/CONTENT_GUIDELINES.md)** - Digest quality standards and formatting
- **[Development Guide](docs/DEVELOPMENT.md)** - Commands, patterns, and best practices

- Always use Context7 MCP when you need library/API documentation, code generation, setup or configuration steps for external libraries without me having to explicitly ask.


## Quick Reference

### Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers at Comcast stay informed on AI/Data trends
- **Voice**: Strategic leadership spanning CTO-level strategy to individual practitioner best practices
- **Sources**: Gmail and Substack RSS feeds
- **Output**: Structured digests with knowledge graph-powered historical context

### Key Commands

```bash
# Setup
source .venv/bin/activate
docker compose up -d
alembic upgrade head

# Ingestion
python -m src.ingestion.gmail
python -m src.ingestion.substack

# Processing
python -m src.processors.summarizer --newsletter-id <id>
python -m src.processors.digest_creator --type daily

# Testing
pytest
pytest tests/test_config/test_models.py -v

# API
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
  ingestion/        # Newsletter fetching (Gmail, RSS)
  processors/       # Core processing (summarize, analyze, create digests)
  storage/          # PostgreSQL + Graphiti/Neo4j
  config/           # Model registry and configuration
  delivery/         # Email and web output
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

### Document Parsing
- **Parser abstraction**: Use `DocumentParser` interface in `src/parsers/base.py` for all document parsing
- **Markdown-centric**: All parsers output markdown via `DocumentContent` model - optimized for LLM consumption
- **ClassVar for class attributes**: Mutable class attributes (like `supported_formats`) must use `ClassVar[set[str]]` to satisfy ruff RUF012
- **Union syntax in isinstance**: Use `isinstance(x, bytes | BinaryIO)` not `isinstance(x, (bytes, BinaryIO))` for Python 3.10+ (UP038)
- **MarkItDown for lightweight parsing**: Office docs, HTML, audio
- **YouTubeParser for transcripts**: Direct youtube-transcript-api usage for timestamp preservation and deep-linking
- **ParserRouter**: Routes documents to appropriate parser based on format detection with fallback support
- **Type ignore for untyped libraries**: Use `# type: ignore[attr-defined]` for libraries without type stubs (e.g., youtube-transcript-api)

### Tool Usage Best Practices
- **Always activate venv**: `source .venv/bin/activate` before running scripts
- **Use fixtures**: Reusable test data with pytest fixtures
- **Error handling**: Don't crash entire batch if one item fails

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
