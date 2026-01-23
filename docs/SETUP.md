# Development Setup

## Prerequisites

- **Python**: 3.11 or higher
- **Docker**: For running local databases (PostgreSQL, Redis, Neo4j)
- **uv**: Python package manager (`pip install uv`)

## Local Development (Recommended)

### 1. Initialize Project

```bash
# Clone repository
git clone <repository-url>
cd agentic-newsletter-aggregator

# Create virtual environment
uv init
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

### 2. Start Local Dependencies

```bash
# Start PostgreSQL, Redis, and Neo4j
docker compose up -d

# Verify services are running
docker ps
```

**Services**:
- PostgreSQL: `localhost:5432` (newsletters database)
- Redis: `localhost:6379` (task queue)
- Neo4j: `localhost:7687` (knowledge graph)

### 3. Install Dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Required: ANTHROPIC_API_KEY (minimum for Claude SDK)
# Optional: OPENAI_API_KEY, GOOGLE_API_KEY (for framework comparison)
```

See [Environment Configuration](#environment-configuration) below for all variables.

### 5. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify database schema
psql postgresql://localhost/newsletters -c "\dt"
```

### 6. Start Graphiti MCP Server (Optional)

For knowledge graph features:

```bash
# Follow Graphiti MCP setup guide
# See: https://github.com/getzep/graphiti/blob/main/mcp_server/README.md
```

### 7. Verify Setup

```bash
# Run tests to verify everything works
pytest tests/test_config/

# Should see: "29 passed"
```

## Supabase Cloud Database (Bring Your Own)

The newsletter aggregator supports **Supabase** as a cloud PostgreSQL option. This follows the "bring your own backend" pattern - each user connects their own Supabase instance and owns all their data.

### Why Supabase?

- **Free tier**: 500MB database, 50 concurrent connections
- **Zero infrastructure**: No Docker or local PostgreSQL needed
- **Production-ready**: Managed backups, automatic SSL, connection pooling
- **Quick start**: Get running in minutes

### Setup Guide

#### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project (note your **project reference ID**)
3. Wait for database provisioning (~2 minutes)

#### 2. Get Database Credentials

1. Go to **Project Settings > Database**
2. Note these values:
   - **Project Reference**: `your-project-ref` (in the URL: `supabase.com/dashboard/project/your-project-ref`)
   - **Database Password**: Set during project creation
   - **Region**: e.g., `us-east-1`

#### 3. Configure Environment

**Option A: Component-based config (Recommended)**

```bash
# .env
SUPABASE_PROJECT_REF=your-project-ref
SUPABASE_DB_PASSWORD=your-database-password
SUPABASE_REGION=us-east-1
SUPABASE_POOLER_MODE=transaction  # or "session" for prepared statements
SUPABASE_AZ=1                     # availability zone (see note below)
```

> **Finding your AZ**: Look at your Supabase connection string - it shows `aws-{AZ}-{region}.pooler.supabase.com`. The number after `aws-` is your AZ (usually 0 or 1).

**Option B: Direct connection string**

```bash
# .env - Get from Supabase Dashboard > Settings > Database > Connection string
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-1-[region].pooler.supabase.com:6543/postgres
```

#### 4. Run Migrations

Migrations work through the **pooler connection** (default):

```bash
# Just run - uses the pooler URL automatically
alembic upgrade head
```

> **Note on Direct Connections**: Supabase free tier direct connections (`db.{project}.supabase.co`) use **IPv6 only**. If your network is IPv4-only, you must use the pooler (which supports both). Most migrations work fine through the pooler.

#### 5. Verify Connection

```bash
# Test database connectivity
python -c "from src.storage.database import health_check, get_provider_name; print(f'Provider: {get_provider_name()}'); print(f'Health: {health_check()}')"

# Expected output:
# Provider: supabase
# Health: True
```

### Connection Pooling Modes

Supabase uses **Supavisor** for connection pooling with two modes:

| Mode | Port | Use Case |
|------|------|----------|
| **Transaction** (default) | 6543 | Most applications - efficient connection reuse |
| **Session** | 5432 | Apps using prepared statements or LISTEN/NOTIFY |

Configure via `SUPABASE_POOLER_MODE=transaction` or `session`.

### Supabase Free Tier Limits

| Resource | Limit |
|----------|-------|
| Database size | 500MB |
| Pooler connections | 50 (IPv4 + IPv6) |
| Direct connections | 10 (IPv6 only) |
| Bandwidth | 2GB/month |

> **IPv6 Note**: Direct connections on free tier resolve to IPv6 only. Use the pooler (default) if your network is IPv4-only.

For production workloads, consider upgrading to a paid plan.

### Troubleshooting Supabase

**Connection refused**:
```bash
# Verify your project is active (not paused)
# Free tier projects pause after 7 days of inactivity
```

**SSL required error**:
```bash
# Ensure sslmode=require (automatic with Supabase provider)
# If using direct URL, add: ?sslmode=require
```

**Direct connection refused (IPv6 issue)**:
```bash
# Supabase free tier direct connections use IPv6 only
# If your network is IPv4-only, use the pooler (default)
# Migrations work fine through the pooler for most DDL operations
alembic upgrade head  # Uses pooler automatically
```

**Connection limit exceeded**:
```bash
# Check current connections in Supabase Dashboard
# Reduce pool_size in code or use transaction pooling mode
```

---

## Neon Serverless PostgreSQL (Bring Your Own)

The newsletter aggregator supports **Neon** as a serverless PostgreSQL option. Neon's architecture is particularly well-suited for AI coding agent workflows, offering instant copy-on-write database branching.

### Why Neon?

- **Instant branching**: Create isolated database copies in milliseconds (any size)
- **Agent-native testing**: Each agent session can use ephemeral branches with real data
- **Scale-to-zero**: Compute automatically suspends when idle, reducing costs
- **Time-travel**: Restore database state to any point within retention window
- **Free tier**: 100 CU-hours/month with 500MB storage

### Setup Guide

#### 1. Create Neon Project

1. Go to [console.neon.tech](https://console.neon.tech) and sign up
2. Create a new project (note your **project ID**)
3. Database is ready immediately (no provisioning wait)

#### 2. Get Connection String

1. Go to **Dashboard > Connection Details**
2. Copy the connection string (pooled recommended for applications)

**Connection string formats**:
- **Pooled** (recommended): `postgresql://user:pass@ep-cool-name-123456-pooler.region.aws.neon.tech/dbname`
- **Direct**: `postgresql://user:pass@ep-cool-name-123456.region.aws.neon.tech/dbname`

#### 3. Configure Environment

**Option A: Connection string only (Simple)**

```bash
# .env - For basic usage
DATABASE_URL=postgresql://user:pass@ep-cool-name-123456-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
```

**Option B: With branch management (For agent workflows)**

```bash
# .env - For programmatic branch management
DATABASE_URL=postgresql://user:pass@ep-cool-name-123456-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
NEON_API_KEY=neon_api_key_...           # From Account Settings > API Keys
NEON_PROJECT_ID=proud-paper-123456      # From Project Settings
NEON_DEFAULT_BRANCH=main                # Default parent for new branches
NEON_DIRECT_URL=...                     # Direct URL for migrations (optional)
```

#### 4. Run Migrations

```bash
# Using pooled connection (works for most migrations)
alembic upgrade head

# If you need direct connection (for complex DDL)
NEON_DIRECT_URL=postgresql://user:pass@ep-cool-name-123456.us-east-2.aws.neon.tech/dbname alembic upgrade head
```

#### 5. Verify Connection

```bash
python -c "from src.storage.database import health_check, get_provider_name; print(f'Provider: {get_provider_name()}'); print(f'Health: {health_check()}')"

# Expected output:
# Provider: neon
# Health: True
```

### Branching for Agent Workflows

Neon's killer feature is instant database branching. Each branch is a copy-on-write clone that shares storage with the parent.

#### Create Feature Branch (CLI)

```bash
# Create branch for feature development
neonctl branches create --name claude/feature-xyz --project-id $NEON_PROJECT_ID

# Get connection string for branch
DATABASE_URL=$(neonctl connection-string claude/feature-xyz --project-id $NEON_PROJECT_ID)

# Work with isolated database...

# Delete when done
neonctl branches delete claude/feature-xyz --project-id $NEON_PROJECT_ID
```

#### Programmatic Branch Management (Python)

```python
from src.storage.providers.neon_branch import NeonBranchManager

manager = NeonBranchManager()

# Create ephemeral branch for testing
async with manager.branch_context("test/my-feature") as conn_str:
    # conn_str is the connection string for the new branch
    # Run tests against isolated database
    pass  # Branch auto-deleted when context exits
```

#### Test Fixtures

```python
import pytest
from tests.integration.fixtures.neon import neon_test_branch

@pytest.mark.asyncio
async def test_with_isolated_database(neon_test_branch):
    """Test runs against ephemeral Neon branch."""
    # neon_test_branch is the connection string
    # Branch is created before test, deleted after
```

#### Test Architecture

The Neon provider has two test suites with different purposes:

| Test File | Type | Speed | Requires Credentials |
|-----------|------|-------|---------------------|
| `tests/test_storage/test_neon_branch.py` | Unit (mocked) | ~1 second | No |
| `tests/integration/test_neon_integration.py` | Integration (real API) | ~30-60 seconds | Yes |

**Unit tests** use `httpx.MockTransport` to simulate API responses:
- Test edge cases (rate limiting, error handling, retries)
- Work offline without Neon credentials
- Run as part of standard `pytest` suite

**Integration tests** create real ephemeral branches:
- Verify actual Neon API behavior
- Test SSL/connection handling with real database
- Auto-skip when `NEON_API_KEY`/`NEON_PROJECT_ID` not set

```bash
# Run unit tests only (no credentials needed)
pytest tests/test_storage/test_neon_branch.py -v

# Run integration tests (requires Neon credentials in .env)
pytest tests/integration/test_neon_integration.py -v
```

### Branch Naming Conventions

| Prefix | Purpose | Example |
|--------|---------|---------|
| `claude/` | Claude Code agent sessions | `claude/feature-auth` |
| `test/` | Automated test isolation | `test/abc123` |
| `preview/` | PR preview environments | `preview/pr-42` |

### Pooled vs Direct Connections

| Connection Type | Use Case | URL Pattern |
|-----------------|----------|-------------|
| **Pooled** (default) | Application queries | `...-pooler.region.aws.neon.tech` |
| **Direct** | Migrations, DDL operations | `...region.aws.neon.tech` (no `-pooler`) |

The provider automatically handles pooled connections. Use `NEON_DIRECT_URL` for migrations if needed.

### Neon Free Tier Limits

| Resource | Limit |
|----------|-------|
| Compute | 100 CU-hours/month |
| Storage | 500MB |
| Branches | 10 |
| Projects | 1 |

Branches share storage with parent, so they don't consume additional storage unless you write new data.

### Troubleshooting Neon

**Connection timeout**:
```bash
# Neon computes scale to zero after 5 minutes of inactivity
# First connection may take 2-5 seconds to "wake up"
# Increase connection timeout if needed
```

**Branch limit reached**:
```bash
# Free tier: 10 branches max
# Delete unused branches:
neonctl branches list --project-id $NEON_PROJECT_ID
neonctl branches delete <branch-name> --project-id $NEON_PROJECT_ID
```

**SSL required error**:
```bash
# Ensure ?sslmode=require in connection string
# Neon requires SSL for all connections
```

---

## Cloud Production (When Ready)

### Deployment Platforms

- **Railway / Render / Fly.io**: Application hosting
- **Supabase**: Managed PostgreSQL with connection pooling (see above)
- **Managed PostgreSQL**: Alternative databases (AWS RDS, Google Cloud SQL, etc.)
- **Managed Redis**: Task queue (Redis Cloud, AWS ElastiCache)
- **Neo4j Aura**: Managed knowledge graph (or self-hosted Neo4j)

### Configuration Strategy

- **Same codebase** for local and production
- **Environment variables** control all configuration
- **No code changes** needed for deployment
- Set `ENVIRONMENT=production` in production `.env`

### Environment-Specific Behaviors

**Development** (`ENVIRONMENT=development`):
- Verbose logging
- Local database URLs
- Debug mode enabled
- Test data fixtures available

**Production** (`ENVIRONMENT=production`):
- Production logging levels
- Managed database URLs
- Security hardening
- Real API keys required

## Environment Configuration

### Required Variables

```bash
# Databases
DATABASE_URL=postgresql://localhost/newsletters
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Agent Framework APIs (minimum: ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-...  # Required for Claude SDK
OPENAI_API_KEY=sk-...         # Optional for framework comparison
GOOGLE_API_KEY=...            # Optional for framework comparison

# Environment
ENVIRONMENT=development  # or production
```

### Supabase Variables (Optional Cloud Database)

```bash
# Supabase Cloud Database (alternative to local PostgreSQL)
DATABASE_PROVIDER=supabase               # Required: explicit provider selection
SUPABASE_PROJECT_REF=your-project-ref    # Project reference ID
SUPABASE_DB_PASSWORD=your-db-password    # Database password
SUPABASE_REGION=us-east-1                # AWS region (default: us-east-1)
SUPABASE_POOLER_MODE=transaction         # Connection pooling mode (default: transaction)
SUPABASE_AZ=1                            # AWS availability zone from connection string (default: 0)
SUPABASE_DIRECT_URL=...                  # Direct connection for migrations (optional)
```

See [Supabase Cloud Database](#supabase-cloud-database-bring-your-own) for setup instructions.

### Neon Variables (Optional Cloud Database)

```bash
# Neon Serverless PostgreSQL (alternative to local or Supabase)
DATABASE_PROVIDER=neon                   # Required: explicit provider selection
DATABASE_URL=postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname
NEON_API_KEY=neon_api_key_...            # API key for branch management (optional)
NEON_PROJECT_ID=proud-paper-123456       # Project ID for branch management (optional)
NEON_DEFAULT_BRANCH=main                 # Default parent branch (default: main)
NEON_REGION=us-east-2                    # Region (auto-detected from URL)
NEON_DIRECT_URL=...                      # Direct connection for migrations (optional)
```

See [Neon Serverless PostgreSQL](#neon-serverless-postgresql-bring-your-own) for setup instructions.

### Optional Variables

```bash
# Gmail Ingestion
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json

# Email Delivery (production only)
SENDGRID_API_KEY=...

# Model Configuration (override defaults)
MODEL_SUMMARIZATION=claude-haiku-4-5
MODEL_THEME_ANALYSIS=claude-sonnet-4-5
MODEL_DIGEST_CREATION=claude-sonnet-4-5
MODEL_HISTORICAL_CONTEXT=claude-haiku-4-5

# Document Parsing (Docling)
ENABLE_DOCLING=true                    # Enable Docling parser (default: true)
DOCLING_ENABLE_OCR=false               # Enable OCR for scanned documents (default: false)
DOCLING_MAX_FILE_SIZE_MB=100           # Maximum file size for Docling (default: 100MB)
DOCLING_TIMEOUT_SECONDS=300            # Processing timeout (default: 300s)
```

See [Model Configuration](MODEL_CONFIGURATION.md) for detailed model selection options.

## Gmail API Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Newsletter Aggregator"
3. Enable Gmail API

### 2. Create OAuth Credentials

1. Navigate to **APIs & Services > Credentials**
2. Create **OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Download credentials as `credentials.json`
5. Place in project root

### 3. First-Time Authorization

```bash
# Run Gmail ingestion (will trigger OAuth flow)
python -m src.ingestion.gmail

# Browser will open for authorization
# After auth, token.json will be saved for future use
```

## Troubleshooting

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Reset database (WARNING: destroys all data)
docker compose down -v
docker compose up -d
alembic upgrade head
```

### Import Errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
uv pip install -r requirements.txt
```

### API Key Issues

```bash
# Verify API keys are set
echo $ANTHROPIC_API_KEY

# Test API connectivity
python -c "from anthropic import Anthropic; print(Anthropic(api_key='$ANTHROPIC_API_KEY').models.list())"
```

### Migration Conflicts

```bash
# Check current migration state
alembic current

# Rollback one migration
alembic downgrade -1

# Re-apply migrations
alembic upgrade head
```

## Next Steps

- **[Configure your models](MODEL_CONFIGURATION.md)** - Select LLMs and providers
- **[Run development commands](DEVELOPMENT.md#development-commands)** - Start processing newsletters
- **[Review content guidelines](CONTENT_GUIDELINES.md)** - Understand digest quality standards
