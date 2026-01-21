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
```

**Option B: Direct connection string**

```bash
# .env - Get from Supabase Dashboard > Settings > Database > Connection string
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

#### 4. Run Migrations

Supabase requires a **direct connection** for migrations (bypasses the connection pooler):

```bash
# Set direct URL for migrations
export SUPABASE_DIRECT_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# Or use the component config (auto-generates direct URL)
alembic upgrade head
```

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
| Concurrent connections | 50 (via pooler) |
| Direct connections | 10 |
| Bandwidth | 2GB/month |

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

**Migration fails through pooler**:
```bash
# Use direct connection for DDL operations
export SUPABASE_DIRECT_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
alembic upgrade head
```

**Connection limit exceeded**:
```bash
# Check current connections in Supabase Dashboard
# Reduce pool_size in code or use transaction pooling mode
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
SUPABASE_PROJECT_REF=your-project-ref    # Project reference ID
SUPABASE_DB_PASSWORD=your-db-password    # Database password
SUPABASE_REGION=us-east-1                # AWS region (default: us-east-1)
SUPABASE_POOLER_MODE=transaction         # Connection pooling mode (default: transaction)
SUPABASE_DIRECT_URL=...                  # Direct connection for migrations (optional)
DATABASE_PROVIDER=supabase               # Explicit provider override (optional, auto-detected)
```

See [Supabase Cloud Database](#supabase-cloud-database-bring-your-own) for setup instructions.

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
