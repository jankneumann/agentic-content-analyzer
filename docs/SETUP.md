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

## Local Supabase Development

For full Supabase dev/prod parity without cloud dependencies, you can run Supabase locally. This provides:

- **Offline development**: No internet connection required
- **Dev/prod parity**: Same APIs as production Supabase
- **CI/CD testing**: Run integration tests against real Supabase APIs
- **Cost savings**: No cloud usage during development

### Quick Start

```bash
# Start local Supabase services
docker compose --profile supabase up -d

# Configure environment for local Supabase
export SUPABASE_LOCAL=true
export DATABASE_PROVIDER=supabase

# Run your application
python -m src.main
```

### Using Supabase CLI (Recommended)

The Supabase CLI provides the most complete local development experience:

```bash
# Install Supabase CLI (macOS)
brew install supabase/tap/supabase

# Initialize Supabase in your project (one-time)
supabase init

# Start local Supabase
supabase start

# Get local credentials
supabase status
```

**Local Service Ports** (Supabase CLI defaults):
| Service | Port | Description |
|---------|------|-------------|
| API Gateway | 54321 | Main Supabase API endpoint |
| PostgreSQL | 54322 | Database (direct connection) |
| Studio | 54323 | Admin UI |
| Inbucket | 54324 | Email testing |

### Docker Compose (Alternative)

For simpler setups without the CLI:

```bash
# Start local Supabase via Docker Compose
docker compose --profile supabase up -d

# Verify services are running
docker ps | grep supabase
```

### Environment Configuration

```bash
# .env for local Supabase development
SUPABASE_LOCAL=true                  # Enable local mode
DATABASE_PROVIDER=supabase           # Use Supabase as database provider
IMAGE_STORAGE_PROVIDER=supabase      # Use Supabase Storage (optional)

# These are auto-configured when SUPABASE_LOCAL=true:
# SUPABASE_URL=http://127.0.0.1:54321
# DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
# SUPABASE_ANON_KEY=<local dev key>
# SUPABASE_SERVICE_ROLE_KEY=<local dev key>
```

### Schema Synchronization

Use the Supabase CLI to sync schema between local and cloud:

```bash
# Generate migration from local changes
supabase db diff -f my_migration

# Push local schema to cloud
supabase db push

# Pull cloud schema to local
supabase db pull

# Link to cloud project (one-time)
supabase link --project-ref your-project-ref
```

### Switching Between Local and Cloud

```bash
# Local development
export SUPABASE_LOCAL=true
supabase start
python -m src.main

# Cloud deployment
export SUPABASE_LOCAL=false
export SUPABASE_PROJECT_REF=your-project-ref
export SUPABASE_DB_PASSWORD=your-password
python -m src.main
```

### Local Supabase Requirements

- Docker Desktop or Docker Engine
- ~2GB RAM for full stack
- Supabase CLI (optional but recommended)
- Ports 54321-54324 available

### Troubleshooting Local Supabase

**Port already in use**:
```bash
# Check what's using the port
lsof -i :54322

# Stop existing containers
docker compose --profile supabase down
```

**Services not starting**:
```bash
# Check container logs
docker compose --profile supabase logs supabase-db
docker compose --profile supabase logs supabase-storage
```

**Storage not working**:
```bash
# Ensure bucket exists (create via API or Studio)
# Local Supabase Storage uses the service role key for auth
```

---

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

### Supabase Test Architecture

The Supabase provider has integration tests that verify real cloud connections:

| Test File | Type | Tests | Requires Credentials |
|-----------|------|-------|---------------------|
| `tests/test_storage/test_providers.py` | Unit (local) | 44 | No |
| `tests/integration/test_supabase_provider.py` | Integration (real API) | 17 | Yes |

**Integration tests** verify:
- **Connection**: Pooled and direct connections, SSL enforcement
- **Health checks**: Provider health check passes
- **Pooling**: Sequential, concurrent, and pool exhaustion recovery
- **Transaction isolation**: Uncommitted data visibility
- **DDL operations**: CREATE/DROP TABLE for migrations
- **Configuration**: URLs, engine options, provider identification

```bash
# Run unit tests only (no credentials needed)
pytest tests/test_storage/test_providers.py -v

# Run integration tests (requires Supabase credentials in .env)
pytest tests/integration/test_supabase_provider.py -v
```

**Auto-skip behavior**: Tests are automatically skipped if `SUPABASE_PROJECT_REF` and `SUPABASE_DB_PASSWORD` are not configured, allowing the full test suite to run without Supabase access.

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

## Railway Deployment (Single-Platform)

Railway provides a unified platform for deploying your entire stack - application, PostgreSQL, and MinIO storage - with simple configuration. This is ideal for teams wanting a single-platform deployment without managing multiple cloud services.

### Why Railway?

- **Single platform**: App, database, and storage in one place
- **Simple pricing**: Usage-based, starting at $5/month (Hobby)
- **Custom images**: Deploy custom PostgreSQL with extensions via GHCR
- **Private networking**: Services communicate over internal network
- **Automatic SSL**: Built-in SSL for all connections

### Custom PostgreSQL Image

Railway's default PostgreSQL doesn't include extensions like pgvector. We provide a custom image with all required extensions:

**Included Extensions**:
- `pgvector` - Vector similarity search
- `pg_search` - Full-text search (ParadeDB BM25)
- `pgmq` - Lightweight message queue
- `pg_cron` - Job scheduling

#### Using Pre-built Image (Recommended)

```bash
# Pull from GitHub Container Registry
docker pull ghcr.io/YOUR_ORG/newsletter-postgres:16-railway

# In Railway Dashboard:
# 1. Create new service > Docker Image
# 2. Enter: ghcr.io/YOUR_ORG/newsletter-postgres:16-railway
# 3. Set environment variables (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
```

#### Building the Image

```bash
# Build locally
cd railway/postgres
docker build -t newsletter-postgres:16-railway .

# Push to your registry
docker tag newsletter-postgres:16-railway ghcr.io/YOUR_ORG/newsletter-postgres:16-railway
docker push ghcr.io/YOUR_ORG/newsletter-postgres:16-railway
```

### Setup Guide

#### 1. Create Railway Project

1. Go to [railway.app](https://railway.app) and sign up
2. Create a new project
3. Note your project URL format: `your-app.railway.app`

#### 2. Deploy Custom PostgreSQL

1. Click **New Service > Docker Image**
2. Enter your GHCR image: `ghcr.io/YOUR_ORG/newsletter-postgres:16-railway`
3. Add environment variables:
   ```
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your-secure-password
   POSTGRES_DB=newsletters
   ```
4. Deploy and wait for service to be ready

#### 3. Deploy MinIO for Storage

1. Click **New Service > Docker Image**
2. Enter: `minio/minio`
3. Add startup command: `server /data --console-address ":9001"`
4. Add environment variables:
   ```
   MINIO_ROOT_USER=minioadmin
   MINIO_ROOT_PASSWORD=your-secure-password
   ```
5. Expose ports 9000 (API) and 9001 (console)
6. Create bucket via MinIO console after deployment

#### 4. Configure Environment

```bash
# .env for Railway deployment
DATABASE_PROVIDER=railway
DATABASE_URL=postgresql://postgres:password@postgres.railway.internal:5432/newsletters
STORAGE_PROVIDER=railway
RAILWAY_MINIO_ENDPOINT=http://minio.railway.internal:9000
RAILWAY_MINIO_BUCKET=newsletter-files
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your-secure-password

# Railway extension configuration (all enabled by default)
RAILWAY_PG_CRON_ENABLED=true
RAILWAY_PGVECTOR_ENABLED=true
RAILWAY_PG_SEARCH_ENABLED=true
RAILWAY_PGMQ_ENABLED=true

# Connection pooling (tuned for Hobby plan by default)
RAILWAY_POOL_SIZE=3        # Increase for Pro/Enterprise
RAILWAY_MAX_OVERFLOW=2     # Increase for Pro/Enterprise
```

#### 5. Run Migrations

```bash
# From your deployment service or locally with DATABASE_URL set
alembic upgrade head
```

#### 6. Verify Connection

```bash
python -c "from src.storage.database import health_check, get_provider_name; print(f'Provider: {get_provider_name()}'); print(f'Health: {health_check()}')"

# Expected output:
# Provider: railway
# Health: True
```

### Connection Pooling by Plan

Railway plan determines optimal pool settings:

| Plan | RAM | `RAILWAY_POOL_SIZE` | `RAILWAY_MAX_OVERFLOW` |
|------|-----|---------------------|------------------------|
| Hobby | 512MB | 3 (default) | 2 (default) |
| Pro | 8GB | 10 | 5 |
| Enterprise | 32GB+ | 20 | 10 |

### Internal vs External Connections

| Connection Type | URL Pattern | Use Case |
|-----------------|-------------|----------|
| **Internal** | `service.railway.internal:5432` | Services within Railway project |
| **External** | `proxy.railway.app:PORT` | Local development, CI/CD |

Railway automatically provides `DATABASE_URL` with internal connection for deployed services.

### GHCR Setup for Private Images

If your repository is private, configure GHCR access:

1. Create GitHub Personal Access Token (PAT) with `read:packages` scope
2. In Railway service settings, add Docker credentials:
   ```
   Registry: ghcr.io
   Username: YOUR_GITHUB_USERNAME
   Password: YOUR_PAT
   ```

For public repositories, no authentication is needed.

### Troubleshooting Railway

**Extension not found**:
```bash
# Verify you're using the custom image, not Railway's default postgres
# Check with: SELECT * FROM pg_extension;
```

**Connection refused (internal)**:
```bash
# Services must be in the same Railway project for internal networking
# Use the external URL for cross-project or local connections
```

**MinIO not accessible**:
```bash
# Ensure RAILWAY_PUBLIC_DOMAIN is set or use explicit RAILWAY_MINIO_ENDPOINT
# Internal: minio.railway.internal:9000
# External: Check Railway service's public domain
```

**Pool exhaustion on Hobby plan**:
```bash
# Reduce pool size or upgrade plan
# Hobby plan has limited connections
RAILWAY_POOL_SIZE=2
RAILWAY_MAX_OVERFLOW=1
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
# Databases - DATABASE_URL is the primary connection URL
# Provider-specific URLs (LOCAL_DATABASE_URL, NEON_DATABASE_URL) override DATABASE_URL when set
DATABASE_URL=postgresql://localhost/newsletters  # Default connection URL
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
# Or use explicit override:
# NEON_DATABASE_URL=postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname
NEON_API_KEY=neon_api_key_...            # API key for branch management (optional)
NEON_PROJECT_ID=proud-paper-123456       # Project ID for branch management (optional)
NEON_DEFAULT_BRANCH=main                 # Default parent branch (default: main)
NEON_REGION=us-east-2                    # Region (auto-detected from URL)
NEON_DIRECT_URL=...                      # Direct connection for migrations (optional)
```

See [Neon Serverless PostgreSQL](#neon-serverless-postgresql-bring-your-own) for setup instructions.

### Railway Variables (Optional Single-Platform Deployment)

```bash
# Railway PostgreSQL (custom image with extensions)
DATABASE_PROVIDER=railway                   # Required: explicit provider selection
DATABASE_URL=postgresql://user:pass@postgres.railway.internal:5432/newsletters

# Or use explicit override:
# RAILWAY_DATABASE_URL=postgresql://user:pass@postgres.railway.internal:5432/newsletters

# Extension configuration (all true by default when using custom image)
RAILWAY_PG_CRON_ENABLED=true                # pg_cron job scheduling
RAILWAY_PGVECTOR_ENABLED=true               # pgvector similarity search
RAILWAY_PG_SEARCH_ENABLED=true              # pg_search (ParadeDB) full-text search
RAILWAY_PGMQ_ENABLED=true                   # pgmq message queue

# Connection pooling (tuned for Railway Hobby plan by default)
RAILWAY_POOL_SIZE=3                         # Connections in pool (Hobby: 3, Pro: 10)
RAILWAY_MAX_OVERFLOW=2                      # Extra connections beyond pool (Hobby: 2, Pro: 5)
RAILWAY_POOL_RECYCLE=300                    # Connection recycle time in seconds
RAILWAY_POOL_TIMEOUT=30                     # Connection timeout in seconds

# Railway MinIO Storage
STORAGE_PROVIDER=railway                    # Use Railway MinIO
RAILWAY_MINIO_ENDPOINT=http://minio.railway.internal:9000  # Internal endpoint
RAILWAY_MINIO_BUCKET=newsletter-files       # MinIO bucket name
MINIO_ROOT_USER=minioadmin                  # MinIO access key
MINIO_ROOT_PASSWORD=your-secure-password    # MinIO secret key
```

See [Railway Deployment](#railway-deployment-single-platform) for setup instructions.

### File Storage Variables (Optional)

The newsletter aggregator supports unified file storage for images, podcasts, and audio digests. Three storage providers are supported with multiple bucket support:

**Buckets**:
- `images` - Newsletter images, YouTube keyframes (default path: `data/images`)
- `podcasts` - Generated podcast audio files (default path: `data/podcasts`)
- `audio-digests` - Audio versions of digests (default path: `data/audio-digests`)

```bash
# Unified Storage Provider: "local" (default), "s3", or "supabase"
STORAGE_PROVIDER=local

# Per-bucket provider overrides (JSON format, optional)
# Example: Store podcasts on S3 while keeping images local
STORAGE_BUCKET_PROVIDERS='{"podcasts": "s3"}'

# Local Storage (default - good for development)
# Default paths are data/{bucket} for each bucket

# S3 Storage (for AWS S3 or S3-compatible services like MinIO)
STORAGE_PROVIDER=s3
IMAGE_STORAGE_BUCKET=newsletter-images   # S3 bucket name for images
AWS_REGION=us-east-1                     # AWS region (default: us-east-1)
AWS_ACCESS_KEY_ID=...                    # Optional - uses boto3 defaults if not set
AWS_SECRET_ACCESS_KEY=...                # Optional - uses boto3 defaults if not set
S3_ENDPOINT_URL=...                      # Optional - for S3-compatible services (MinIO, etc.)

# Supabase Storage (uses Supabase's S3-compatible object storage)
STORAGE_PROVIDER=supabase
SUPABASE_STORAGE_BUCKET=images           # Supabase bucket name (default: images)
SUPABASE_ACCESS_KEY_ID=xxx               # S3 access key ID (from Supabase Dashboard)
SUPABASE_SECRET_ACCESS_KEY=xxx           # S3 secret access key (from Supabase Dashboard)
SUPABASE_STORAGE_PUBLIC=false            # Whether bucket is public (default: false)
# Note: Also requires SUPABASE_PROJECT_REF and SUPABASE_REGION from database config

# Legacy image storage config (still works for backward compatibility)
IMAGE_STORAGE_PROVIDER=local
IMAGE_STORAGE_PATH=data/images           # Local directory for images (default: data/images)

# Common Settings
IMAGE_MAX_SIZE_MB=10                     # Maximum image file size (default: 10MB)
ENABLE_IMAGE_EXTRACTION=true             # Enable extraction from HTML/PDF (default: true)
ENABLE_YOUTUBE_KEYFRAMES=false           # Enable YouTube keyframe extraction (default: false)
```

#### File Serving API

Files are served via a unified endpoint with range request support for audio streaming:

```
GET /api/v1/files/{bucket}/{path}
```

- **bucket**: One of `images`, `podcasts`, or `audio-digests`
- **path**: File path within the bucket (e.g., `2025/01/24/filename.mp3`)

Features:
- Content-Type detection via file extension
- Range request support for audio/video seeking
- Signed URL redirect for cloud storage (S3, Supabase)
- Cache headers for performance

#### Supabase Storage Setup

1. In Supabase Dashboard, go to **Storage** > **New bucket**
2. Create a bucket named `images` (or your preferred name)
3. Set bucket privacy (public for direct URLs, private for authenticated access)
4. Go to **Project Settings > API > S3 Access Keys**
5. Generate S3 access keys and add to your `.env`:
   - `SUPABASE_ACCESS_KEY_ID`
   - `SUPABASE_SECRET_ACCESS_KEY`

> **Note**: S3 access keys provide full storage access. Keep them secure and never expose them to clients.

### Observability Variables (Optional)

The newsletter aggregator supports pluggable observability via a provider factory pattern. Two layers work together:

1. **LLM Observability**: Traces LLM calls (model, tokens, prompt/completion) via the selected provider
2. **Infrastructure Telemetry**: Auto-instruments FastAPI, SQLAlchemy, and httpx via OpenTelemetry

```bash
# Provider selection (default: noop — zero overhead)
OBSERVABILITY_PROVIDER=noop          # noop, opik, braintrust, or otel

# OpenTelemetry infrastructure (auto-instrumentation)
OTEL_ENABLED=false                   # Enable OTel auto-instrumentation
OTEL_SERVICE_NAME=newsletter-aggregator
OTEL_EXPORTER_OTLP_ENDPOINT=        # OTLP HTTP endpoint
OTEL_EXPORTER_OTLP_HEADERS=         # Comma-separated key=value pairs
OTEL_LOG_PROMPTS=false               # Log prompt/completion text (PII risk)

# Opik (Comet Cloud or self-hosted)
OPIK_API_KEY=                        # Comet Cloud API key
OPIK_WORKSPACE=                      # Comet Cloud workspace
OPIK_PROJECT_NAME=newsletter-aggregator

# Braintrust (cloud)
BRAINTRUST_API_KEY=                  # Required when using braintrust provider
BRAINTRUST_PROJECT_NAME=newsletter-aggregator
BRAINTRUST_API_URL=https://api.braintrust.dev

# Health checks
HEALTH_CHECK_TIMEOUT_SECONDS=5       # Timeout for readiness probe checks
```

**Provider quick-start examples**:

```bash
# Braintrust (cloud — recommended for evaluations and scoring)
OBSERVABILITY_PROVIDER=braintrust
BRAINTRUST_API_KEY=sk-xxx
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.braintrust.dev/otel/v1/traces

# Opik (self-hosted via Docker)
OBSERVABILITY_PROVIDER=opik
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:5173/api/v1/private/otel

# Generic OTel (any OTLP backend — Jaeger, Grafana Tempo, etc.)
OBSERVABILITY_PROVIDER=otel
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

**Testing with local Opik (Docker)**:

A `docker-compose.opik.yml` is included to run Opik self-hosted alongside your normal dev stack with no port conflicts:

```bash
# Start your normal stack (postgres, redis, neo4j)
docker compose up -d

# Start Opik (separate Docker project — no port conflicts)
docker compose -f docker-compose.opik.yml -p opik up -d

# Wait ~60s for Opik backend to run migrations, then open:
#   Opik UI:   http://localhost:5173
#   Opik API:  http://localhost:8080
```

Configure `.env` to send traces to local Opik:

```bash
OBSERVABILITY_PROVIDER=opik
OTEL_ENABLED=true
# No OTEL_EXPORTER_OTLP_ENDPOINT needed — defaults to http://localhost:5173/api/v1/private/otel
OPIK_PROJECT_NAME=newsletter-aggregator
OTEL_LOG_PROMPTS=true                   # Optional: see prompt/completion text in Opik
```

Run the app and trigger an LLM call (chat, summarizer, etc.) — traces appear in the Opik UI at `http://localhost:5173`.

Port isolation: Opik's internal Redis and Python backend are **not** exposed to the host, so they won't conflict with our Redis (6379) or FastAPI (8000). Only the Opik frontend (5173) and backend API (8080) are exposed.

Tear down when done:

```bash
docker compose -f docker-compose.opik.yml -p opik down
```

**Health endpoints**:
- `GET /health` — Liveness probe (always 200 if process alive)
- `GET /ready` — Readiness probe (200 if database OK, 503 otherwise)

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

# Podcast Ingestion (STT)
PODCAST_STT_PROVIDER=openai             # STT provider (default: openai)
PODCAST_MAX_DURATION_MINUTES=120        # Max audio length for transcription (default: 120)
PODCAST_TEMP_DIR=/tmp/podcast_audio     # Temp directory for audio downloads
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
