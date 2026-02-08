# Agentic Newsletter Aggregator

Use an agentic AI solution to summarize AI newsletters into daily and weekly digests.

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) package manager
- API keys (Anthropic, optionally OpenAI/Google)

### Installation

1. **Install uv** (if not already installed):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

2. **Clone and setup**:
```bash
cd agentic-newsletter-aggregator

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

3. **Install dependencies**:
```bash
uv sync
```

4. **Set up environment**:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

5. **Start local services** (PostgreSQL, Redis, Neo4j):
```bash
docker compose up -d
```

6. **Initialize database**:
```bash
# Create initial migration
alembic revision --autogenerate -m "initial schema"

# Apply migration
alembic upgrade head
```

7. **Verify setup**:
```bash
# Check that all services are running
docker compose ps

# Should show postgres, redis, and neo4j as healthy
```

### Using the CLI

The `aca` CLI is installed as a Python entry point when you install the package (step 3). After activating your virtual environment, it's available as a command:

```bash
# Show all available commands
aca --help

# Verify services are connected
aca manage verify-setup

# Example: ingest content, summarize, and create a digest
aca ingest gmail
aca summarize pending
aca create-digest daily

# Or run the full pipeline in one command
aca pipeline daily
```

See the [Workflow](#workflow) section below for detailed usage.

## Project Structure

```
src/
  agents/           # Agent framework implementations
    base.py         # Abstract base classes
    claude/         # Claude SDK agents (primary)
    openai/         # OpenAI SDK agents
    google/         # Google ADK agents
    microsoft/      # MS Agent Framework agents
  ingestion/        # Content fetching
    gmail.py        # Gmail API integration
    substack.py     # RSS feed parser
  models/           # Data models (Pydantic + SQLAlchemy)
    content.py      # Content model
    summary.py      # Summary model
    digest.py       # Digest model
    revision.py     # Revision context models
  storage/          # Data persistence
    database.py     # PostgreSQL connection
    graphiti_client.py  # Graphiti MCP integration
  processors/       # Core processing
    summarizer.py
    theme_analyzer.py
    digest_creator.py
    digest_reviser.py  # AI-powered digest revision
  services/         # Business logic layer
    review_service.py  # Digest review operations
  delivery/         # Output channels
    email.py
    web.py
  tasks/            # Celery tasks
  api/              # FastAPI app

scripts/
  review_digest.py  # Interactive digest review CLI
  generate_daily_digest.py
  generate_weekly_digest.py
```

## Workflow

### 1. Content Ingestion
```bash
# Fetch from Gmail newsletters
aca ingest gmail

# Fetch from RSS feeds (Substack, etc.)
aca ingest rss

# Fetch from YouTube playlists
aca ingest youtube

# Fetch from podcast feeds
aca ingest podcast

# Ingest local files
aca ingest files <path...>
```

### 2. Summarization & Digest Generation
```bash
# Summarize all pending content
aca summarize pending

# Generate daily digest
aca create-digest daily

# Generate weekly digest
aca create-digest weekly

# Or run the full pipeline (ingest → summarize → digest)
aca pipeline daily
```

### 3. Review & Delivery
```bash
# List all digests pending review
aca review list

# View digest content
aca review view <id>

# Analyze themes across content
aca analyze themes

# Generate podcast script from a digest
aca podcast generate --digest-id <id>
```

See [docs/REVIEW_SYSTEM.md](docs/REVIEW_SYSTEM.md) for detailed documentation.

## Development

### Database Migrations

```bash
# Create a new migration after modifying models
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Running Tests

**Unit Tests:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_processors/test_summarizer.py

# Run specific test
pytest -k "test_newsletter_parsing"
```

**Integration Tests:**
Integration tests require dedicated test infrastructure to avoid affecting dev/prod data.

```bash
# Setup test infrastructure (one-time)
make test-setup
# Creates: PostgreSQL test DB + Neo4j test instance (port 7688)

# Run integration tests
make test-integration
# Or: pytest tests/integration/ -v

# Teardown test infrastructure (optional)
make test-teardown  # Stop but keep data
make test-clean     # Stop and delete all test data
```

**Test Infrastructure Details:**
- **PostgreSQL**: Separate `newsletters_test` database with transaction rollback
- **Neo4j**: Dedicated test instance on port 7688 (dev/prod uses 7687)
  - HTTP: http://localhost:7475
  - Bolt: bolt://localhost:7688
  - Automatic cleanup after each test (safe, isolated from dev data)

**Why separate Neo4j instance?**
Neo4j Community Edition doesn't support multiple databases. Using a separate Docker container on a different port ensures test cleanup never affects your production knowledge graph data.

### Code Quality

```bash
# Lint code
ruff check src/

# Auto-fix linting issues
ruff check --fix src/

# Type checking
mypy src/
```

### Local Services

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f postgres

# Restart a service
docker compose restart postgres

# Clean up volumes (WARNING: deletes all data)
docker compose down -v
```

### Database Access

```bash
# PostgreSQL
docker exec -it newsletter-postgres psql -U newsletter_user -d newsletters

# Redis CLI
docker exec -it newsletter-redis redis-cli

# Neo4j Browser
# Open http://localhost:7474
# Username: neo4j
# Password: newsletter_password
```

## Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials and save as `credentials.json` in project root
6. Run the initial authentication:
```bash
python scripts/setup_gmail.py  # TODO: create this script
```

## Environment Variables

See `.env.example` for all configuration options. Key variables:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-xxx

# Database (defaults work with docker-compose)
DATABASE_URL=postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters
REDIS_URL=redis://localhost:6379/0
NEO4J_URI=bolt://localhost:7687

# Optional (for framework comparison)
OPENAI_API_KEY=sk-xxx
GOOGLE_API_KEY=xxx
```

## Next Steps

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full development roadmap.

**Immediate tasks:**
1. Set up Gmail API access
2. Implement newsletter ingestion from Gmail
3. Implement Substack RSS ingestion
4. Set up Graphiti MCP server
5. Build first newsletter summarization with Claude SDK

## Documentation

- [CLAUDE.md](CLAUDE.md) - Guidance for Claude Code working in this repository
- [PROJECT_PLAN.md](PROJECT_PLAN.md) - Complete project plan and roadmap
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development guide and commands
- [docs/REVIEW_SYSTEM.md](docs/REVIEW_SYSTEM.md) - Human review system documentation
- [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) - Model selection and configuration
- [docs/CONTENT_GUIDELINES.md](docs/CONTENT_GUIDELINES.md) - Content quality guidelines

## License

See [LICENSE](LICENSE) file for details.
