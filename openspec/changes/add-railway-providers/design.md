## Context

Railway is a cloud platform that provides managed infrastructure services including PostgreSQL and MinIO (S3-compatible storage). The project needs to support Railway as a deployment target to enable single-platform deployments.

**Key Railway characteristics:**
- Services communicate via private network (RAILWAY_PRIVATE_DOMAIN)
- External access via TCP proxy (RAILWAY_TCP_PROXY_DOMAIN)
- Environment variables are auto-injected for service connections
- SSL certificates are auto-generated and enforced
- PostgreSQL uses standard port 5432 internally
- Supports custom Docker images for enhanced PostgreSQL with extensions

## Goals / Non-Goals

**Goals:**
- Support Railway PostgreSQL as a database provider
- Support Railway MinIO as a storage provider
- Maintain consistency with existing provider patterns
- Enable zero-config deployment when running on Railway
- Provide feature parity with other providers via PostgreSQL extensions (pgvector, pg_search, pgmq, pg_cron)

**Non-Goals:**
- Railway-specific migration tooling (use standard Alembic)
- Multi-region Railway deployments
- Railway-specific caching (Redis is separate)
- Native Railway CLI integration

## Decisions

### Decision 1: Railway Database Provider Implementation

**What**: Create `RailwayProvider` class following the existing `NeonProvider` pattern.

**Why**: Railway PostgreSQL is standard PostgreSQL with connection pooling. The implementation is simpler than Neon (no URL rewriting for pooler) but needs Railway-specific connection handling.

**Railway connection model:**
```
Internal: DATABASE_URL = postgresql://user:pass@service.railway.internal:5432/railway
External: DATABASE_PUBLIC_URL = postgresql://user:pass@proxy.railway.app:PORT/railway
```

**Implementation approach:**
```python
class RailwayProvider:
    def __init__(self, database_url: str | None = None):
        self._database_url = database_url

    @property
    def name(self) -> str:
        return "railway"

    def get_engine_url(self) -> str:
        return self._database_url  # Use internal URL when available

    def get_engine_options(self) -> dict[str, Any]:
        return {
            "pool_pre_ping": True,
            "pool_size": 5,        # Conservative for shared hosting
            "max_overflow": 5,
            "pool_recycle": 300,   # 5 min recycle for cloud
            "pool_timeout": 30,
            "echo": False,
            "connect_args": {
                "sslmode": "require",  # Railway enforces SSL
            },
        }

    def supports_pg_cron(self) -> bool:
        return self._pg_cron_enabled  # True when using custom image with pg_cron
```

**Alternatives considered:**
- Reuse LocalPostgresProvider: Rejected because Railway has different SSL and pool requirements
- Reuse NeonProvider: Rejected because Railway doesn't need pooler URL conversion

### Decision 2: Custom PostgreSQL Image with Extensions

**What**: Provide a custom PostgreSQL Docker image with pgvector, pg_search, pgmq, and pg_cron extensions pre-installed for Railway deployment.

**Why**: Railway's default PostgreSQL image lacks these extensions. To achieve feature parity with Supabase/Neon (which include pgvector and pg_cron), we need a custom image. Additionally, pg_search (full-text search) and pgmq (message queue) provide valuable capabilities for the newsletter aggregator.

**Extensions included:**

| Extension | Version | Purpose |
|-----------|---------|---------|
| pgvector | 0.7.x | Vector similarity search for embeddings |
| pg_search (ParadeDB) | 0.13.x | Full-text search with BM25 ranking |
| pgmq | 1.4.x | Lightweight message queue in PostgreSQL |
| pg_cron | 1.6.x | Job scheduling within PostgreSQL |

**Custom Dockerfile (`railway/postgres/Dockerfile`) - Multi-stage build:**
```dockerfile
#############################################
# Stage 1: Builder - compile all extensions
#############################################
FROM postgres:16-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    postgresql-server-dev-16 \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for pg_search and pgmq)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install pgrx (PostgreSQL extension framework)
RUN cargo install --locked cargo-pgrx@0.12.6 \
    && cargo pgrx init --pg16 $(which pg_config)

# Install pgvector
RUN cd /tmp \
    && git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make && make install \
    && rm -rf /tmp/pgvector

# Install pg_cron
RUN cd /tmp \
    && git clone --branch v1.6.4 https://github.com/citusdata/pg_cron.git \
    && cd pg_cron \
    && make && make install \
    && rm -rf /tmp/pg_cron

# Install pgmq
RUN cd /tmp \
    && git clone --branch v1.4.4 https://github.com/tembo-io/pgmq.git \
    && cd pgmq/pgmq-extension \
    && cargo pgrx install --release \
    && rm -rf /tmp/pgmq

# Install pg_search (ParadeDB)
RUN cd /tmp \
    && git clone --branch v0.13.0 https://github.com/paradedb/paradedb.git \
    && cd paradedb/pg_search \
    && cargo pgrx install --release \
    && rm -rf /tmp/paradedb

#############################################
# Stage 2: Runtime - minimal production image
#############################################
FROM postgres:16-bookworm

# Copy compiled extensions from builder
COPY --from=builder /usr/share/postgresql/16/extension/ /usr/share/postgresql/16/extension/
COPY --from=builder /usr/lib/postgresql/16/lib/ /usr/lib/postgresql/16/lib/

# Configure PostgreSQL to load extensions requiring shared_preload_libraries
RUN echo "shared_preload_libraries = 'pg_cron,pgmq,pg_search'" >> /usr/share/postgresql/postgresql.conf.sample

# Initialization script to create extensions
COPY init-extensions.sql /docker-entrypoint-initdb.d/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pg_isready -U postgres || exit 1
```

**Image size comparison:**
- Single-stage build: ~2.1 GB (includes Rust toolchain, build tools)
- Multi-stage build: ~450 MB (runtime only)

**Extension initialization (`railway/postgres/init-extensions.sql`):**
```sql
-- Enable extensions in the default database
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS pgmq;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Grant pg_cron permissions to the database user
GRANT USAGE ON SCHEMA cron TO postgres;
```

**Railway deployment options:**

1. **GitHub-linked deployment**: Point Railway to a repo with the Dockerfile
2. **Pre-built image**: Push to Docker Hub/GHCR and reference in Railway
3. **Railway template**: Create a reusable template for the community

**Alternatives considered:**
- **Use ParadeDB image directly**: Has pgvector and pg_search but lacks pgmq and pg_cron
- **Use Tembo cloud**: Great extensions but adds another service dependency
- **Install extensions at runtime**: Rejected; requires superuser and build tools in production

### Decision 3: Pre-built Image Registry (GHCR)

**What**: Publish pre-built PostgreSQL images to GitHub Container Registry (GHCR) via CI workflow.

**Why**: Building the custom image takes 10-15 minutes due to Rust compilation. Pre-built images enable instant Railway deployments and ensure reproducible builds.

**Image naming:**
```
ghcr.io/jankneumann/newsletter-postgres:16-railway
ghcr.io/jankneumann/newsletter-postgres:16-railway-v1.0.0  # Tagged releases
```

**CI workflow (`.github/workflows/build-railway-postgres.yml`):**
```yaml
name: Build Railway PostgreSQL Image

on:
  push:
    paths:
      - 'railway/postgres/**'
    branches: [main]
  workflow_dispatch:  # Manual trigger

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository_owner }}/newsletter-postgres

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./railway/postgres
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:16-railway
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:16-railway-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Railway deployment with pre-built image:**
```toml
# railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile.railway-postgres"

# Or reference GHCR directly in Railway dashboard
# Image: ghcr.io/jankneumann/newsletter-postgres:16-railway
```

**GHCR Setup Instructions:**

1. **No additional setup required for public repos** - The `GITHUB_TOKEN` automatically has `packages:write` permission when specified in the workflow.

2. **Make the package public** (recommended for Railway access):
   - Go to GitHub → Your Profile → Packages
   - Find `newsletter-postgres` package
   - Settings → Change visibility → Public
   - This allows Railway to pull without authentication

3. **For private packages** (if keeping repo private):
   - Create a Personal Access Token (PAT) with `read:packages` scope
   - In Railway dashboard, add the token as a secret
   - Configure Railway to use authenticated pulls:
     ```
     # Railway Variables
     GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
     ```

4. **First-time workflow run**:
   - The workflow creates the package automatically on first push
   - Initial build takes ~15 minutes (Rust compilation)
   - Subsequent builds use GitHub Actions cache (~5 minutes)

5. **Verify package is accessible**:
   ```bash
   # Public package - no auth needed
   docker pull ghcr.io/jankneumann/newsletter-postgres:16-railway

   # Private package - requires auth
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   docker pull ghcr.io/jankneumann/newsletter-postgres:16-railway
   ```

### Decision 4: Backup Strategy

**What**: Document backup approaches for Railway PostgreSQL since custom images don't get Railway's managed backups.

**Why**: Railway's default PostgreSQL includes automatic backups, but custom Docker images require manual backup configuration. Data loss prevention is critical for production deployments.

**Backup options:**

1. **pg_cron + pg_dump to MinIO** (recommended for Railway-only deployments):
```sql
-- Schedule daily backup at 3 AM UTC
SELECT cron.schedule('daily-backup', '0 3 * * *', $$
    COPY (SELECT 1) TO PROGRAM 'pg_dump -Fc newsletters |
        aws s3 cp - s3://backups/newsletters-$(date +%Y%m%d).dump
        --endpoint-url $MINIO_ENDPOINT'
$$);
```

2. **External backup service** (for critical production):
   - Use Railway's `DATABASE_PUBLIC_URL` with external backup tools
   - Services: pgBackRest, Barman, or managed backup services

3. **Railway volume snapshots**:
   - Railway volumes support snapshots via dashboard
   - Manual process, suitable for pre-migration backups

**Backup settings:**
```python
# settings.py
railway_backup_enabled: bool = True
railway_backup_schedule: str = "0 3 * * *"  # Cron expression
railway_backup_retention_days: int = 7
railway_backup_bucket: str = "backups"
```

**Recovery procedure:**
```bash
# Download backup from MinIO
aws s3 cp s3://backups/newsletters-20240115.dump ./backup.dump \
    --endpoint-url $MINIO_ENDPOINT

# Restore to PostgreSQL
pg_restore -d newsletters ./backup.dump
```

### Decision 5: Connection Pool Sizing by Railway Plan

**What**: Configure connection pool sizes based on Railway plan resource limits.

**Why**: Railway plans have different resource allocations. Over-provisioning connections wastes memory; under-provisioning causes connection errors.

**Railway plan limits:**

| Plan | RAM | vCPU | Recommended pool_size | max_overflow |
|------|-----|------|----------------------|--------------|
| Hobby | 512 MB | 0.5 | 3 | 2 |
| Pro | 8 GB | 2 | 10 | 10 |
| Enterprise | 32 GB+ | 8+ | 20 | 20 |

**PostgreSQL connection formula:**
- Each connection uses ~5-10 MB RAM
- Reserve 50% RAM for PostgreSQL operations
- `max_connections = (available_ram_mb * 0.5) / 10`

**Dynamic pool configuration:**
```python
class RailwayProvider:
    def get_engine_options(self) -> dict[str, Any]:
        # Allow override via environment
        pool_size = int(os.environ.get("RAILWAY_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("RAILWAY_MAX_OVERFLOW", "5"))

        return {
            "pool_pre_ping": True,
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_recycle": 300,
            "pool_timeout": 30,
            "echo": False,
            "connect_args": {
                "sslmode": "require",
            },
        }
```

**Settings:**
```python
# settings.py
railway_pool_size: int = 3        # Default for Hobby plan
railway_max_overflow: int = 2
railway_pool_recycle: int = 300   # 5 minutes
railway_pool_timeout: int = 30    # 30 seconds
```

**Documentation guidance:**
- Hobby plan: Use defaults (pool_size=3)
- Pro plan: Increase to pool_size=10 for high-traffic apps
- Monitor with `pg_stat_activity` to tune

### Decision 6: Railway Storage Provider Implementation

**What**: Create `RailwayFileStorage` extending `S3FileStorage` with Railway MinIO defaults.

**Why**: MinIO on Railway uses standard S3 API but has Railway-specific endpoint discovery and credential handling.

**Railway MinIO environment:**
```
MINIO_ROOT_USER=auto-generated
MINIO_ROOT_PASSWORD=auto-generated-48-char
MINIO_BUCKET=user-defined
RAILWAY_PUBLIC_DOMAIN=minio-xxx.railway.app
```

**Implementation approach:**
```python
class RailwayFileStorage(S3FileStorage):
    def __init__(
        self,
        bucket: str | None = None,
        storage_bucket: str = "images",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        # Use Railway-provided credentials and endpoint
        endpoint = endpoint_url or f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN')}"
        access_key = access_key_id or os.environ.get("MINIO_ROOT_USER")
        secret_key = secret_access_key or os.environ.get("MINIO_ROOT_PASSWORD")

        super().__init__(
            bucket=bucket or os.environ.get("MINIO_BUCKET"),
            storage_bucket=storage_bucket,
            endpoint_url=endpoint,
            region="us-east-1",  # MinIO doesn't require real region
            access_key_id=access_key,
            secret_access_key=secret_key,
        )

    @property
    def provider_name(self) -> str:
        return "railway"
```

**Alternatives considered:**
- Use S3FileStorage directly: Possible but requires manual endpoint configuration
- Create separate MinIO provider: Rejected to avoid duplication; Railway provider handles Railway-specific discovery

### Decision 7: Environment Variable Strategy

**What**: Use Railway's auto-injected variables with explicit overrides.

**Priority order for database:**
1. `RAILWAY_DATABASE_URL` (explicit override)
2. `DATABASE_URL` with Railway detection (contains `.railway.internal` or `.railway.app`)
3. Generic `DATABASE_URL` as fallback

**Priority order for storage:**
1. Explicit `RAILWAY_MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
2. Auto-discovery from `RAILWAY_PUBLIC_DOMAIN` for endpoint

**Settings additions:**
```python
# settings.py

# Database connection
railway_database_url: str | None = None

# Storage connection
railway_minio_endpoint: str | None = None
railway_minio_bucket: str | None = None
minio_root_user: str | None = None
minio_root_password: str | None = None

# Extension support flags (enabled when using custom PostgreSQL image)
railway_pg_cron_enabled: bool = True   # Default True assuming custom image
railway_pgvector_enabled: bool = True
railway_pg_search_enabled: bool = True
railway_pgmq_enabled: bool = True

# Connection pool settings (adjust based on Railway plan)
railway_pool_size: int = 3        # Default for Hobby plan (512 MB RAM)
railway_max_overflow: int = 2
railway_pool_recycle: int = 300   # 5 minutes
railway_pool_timeout: int = 30    # 30 seconds

# Backup settings
railway_backup_enabled: bool = True
railway_backup_schedule: str = "0 3 * * *"  # Daily at 3 AM UTC
railway_backup_retention_days: int = 7
railway_backup_bucket: str = "backups"
```

### Decision 8: Provider Detection Pattern

**What**: Maintain explicit `DATABASE_PROVIDER=railway` requirement (no auto-detection from URL).

**Why**: Consistent with the refactoring done for Supabase/Neon. Auto-detection was explicitly removed in favor of explicit provider selection.

```python
# Validation in settings.py
case "railway":
    effective_url = self.railway_database_url or self.database_url
    if not effective_url:
        raise ValueError(
            "DATABASE_PROVIDER=railway requires DATABASE_URL or RAILWAY_DATABASE_URL"
        )
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Railway service endpoints may change | Use environment variables, not hardcoded URLs |
| MinIO on Railway has single-volume limitation | Document limitation; use external S3 for large storage needs |
| Custom PostgreSQL image requires maintenance | Pin extension versions; document upgrade process |
| Custom image build time (~10-15 min) | Pre-build and push to GHCR; Railway caches layers |
| Extension compatibility with PostgreSQL upgrades | Test extensions with new PG versions before upgrading base image |
| Railway cold starts affect connection | Use `pool_pre_ping=True` and appropriate timeouts |
| No managed backups for custom images | Implement pg_cron backup jobs to MinIO; document recovery |
| Connection exhaustion on small plans | Configure pool sizes per Railway plan; document limits |
| GHCR rate limits | Use GitHub Actions cache; Railway caches pulled images |

## Migration Plan

1. Add Railway provider code (non-breaking)
2. Add documentation
3. Users opt-in by setting `DATABASE_PROVIDER=railway` and `STORAGE_PROVIDER=railway`

**Rollback**: Simply change provider back to previous setting; no data migration needed.

## Open Questions

1. **Should we support Railway's private networking?** - Initial implementation uses public URLs; private networking can be added later if needed
2. **Should Railway MinIO use internal or public endpoint?** - Default to public for simplicity; document private networking option
3. **Should we add Railway-specific health checks?** - Standard PostgreSQL health check should work; monitor and adjust if needed
