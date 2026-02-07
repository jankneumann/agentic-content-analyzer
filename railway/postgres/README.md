# Railway PostgreSQL with Extensions

Custom PostgreSQL 17 image with production-ready extensions for the Newsletter Aggregator.

## Extensions Included

| Extension | Version | Purpose |
|-----------|---------|---------|
| pgvector | 0.8.0 | Vector similarity search for AI embeddings |
| pg_search | 0.13.0 | Full-text search with BM25 ranking (ParadeDB) |
| pgmq | 1.4.4 | Lightweight message queue in PostgreSQL |
| pg_cron | 1.6.4 | Job scheduling within PostgreSQL |

## Usage

### Option 1: Use Pre-built Image (Recommended)

Pull the pre-built image from GitHub Container Registry:

```bash
docker pull ghcr.io/jankneumann/newsletter-postgres:17-railway
```

In Railway dashboard:
1. Create a new service
2. Select "Docker Image"
3. Enter: `ghcr.io/jankneumann/newsletter-postgres:17-railway`

### Option 2: Build Locally

```bash
# Build the image
docker build -t newsletter-postgres:railway ./railway/postgres

# Run locally for testing
docker run -d \
  --name newsletter-postgres \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=newsletters \
  -v postgres_data:/var/lib/postgresql/data \
  newsletter-postgres:railway
```

### Option 3: Deploy from Dockerfile on Railway

1. Push this directory to your repo
2. In Railway, create a new service from your repo
3. Set the Dockerfile path to `railway/postgres/Dockerfile`

## Verify Extensions

After the container starts, connect and verify extensions:

```sql
-- List available extensions
SELECT * FROM pg_available_extensions
WHERE name IN ('vector', 'pg_search', 'pgmq', 'pg_cron');

-- Check loaded extensions
SELECT * FROM pg_extension;

-- Test pgvector
CREATE TABLE test_vectors (id serial PRIMARY KEY, embedding vector(3));
INSERT INTO test_vectors (embedding) VALUES ('[1,2,3]'), ('[4,5,6]');
SELECT * FROM test_vectors ORDER BY embedding <-> '[3,3,3]' LIMIT 1;
DROP TABLE test_vectors;

-- Test pg_cron
SELECT cron.schedule('test-job', '* * * * *', 'SELECT 1');
SELECT * FROM cron.job;
SELECT cron.unschedule('test-job');
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | (required) |
| `POSTGRES_DB` | Default database name | `postgres` |
| `POSTGRES_USER` | Database user | `postgres` |

## Railway-Specific Configuration

Railway automatically injects:
- `DATABASE_URL` - Connection string for internal services
- `DATABASE_PUBLIC_URL` - Connection string for external access

Set `DATABASE_PROVIDER=railway` in your application to use the Railway provider.

## Connection Pool Settings (Hobby Plan)

For Railway Hobby plan (512 MB RAM):
```bash
RAILWAY_POOL_SIZE=3
RAILWAY_MAX_OVERFLOW=2
```

For Railway Pro plan (8 GB RAM):
```bash
RAILWAY_POOL_SIZE=10
RAILWAY_MAX_OVERFLOW=10
```

## Backups

Since this is a custom image, Railway's managed backups are not available.
Use pg_cron to schedule backups to MinIO:

```sql
-- Schedule daily backup at 3 AM UTC
SELECT cron.schedule('daily-backup', '0 3 * * *', $$
    COPY (SELECT 1) TO PROGRAM 'pg_dump -Fc $POSTGRES_DB |
        aws s3 cp - s3://backups/newsletter-$(date +%Y%m%d).dump
        --endpoint-url $MINIO_ENDPOINT'
$$);
```

## Build Time

- First build: ~10 minutes (Rust compilation for pg_search; pgmq is pure SQL)
- Cached builds: ~5 minutes (with GitHub Actions cache)

## Image Size

- Multi-stage build: ~450 MB
- Single-stage build: ~2.1 GB (not recommended)
