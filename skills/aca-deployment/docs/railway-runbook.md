# Railway Operations Runbook

Railway hosts the compute layer: API backend, frontend, MinIO storage, and optional worker processes.

## Architecture

```
Railway Project
  ├── backend        — FastAPI (Python), port ${PORT:-8000}
  ├── frontend       — Vite/React, static build served by nginx/caddy
  ├── minio          — S3-compatible object storage (images, podcasts, audio-digests)
  └── (worker)       — Optional standalone queue worker
```

## CLI Reference

```bash
# Authentication
railway login                          # Browser-based OAuth
railway whoami                         # Verify auth

# Project linking (one-time)
railway link                           # Interactive project/environment selector

# Status & Deployments
railway status                         # Current project status
railway deployments list --limit 10    # Recent deployments

# Logs
railway logs                           # Tail default service logs
railway logs --service backend         # Specific service
railway logs --service frontend

# Environment Variables
railway variables list                 # Show all variables
railway variables set KEY=VALUE        # Set a variable (triggers redeploy)

# Service Management
railway up --detach                    # Deploy current code
railway up --service backend --detach  # Deploy specific service
railway service restart --service backend
```

## Profiles

| Profile | Database | Storage | Use Case |
|---------|----------|---------|----------|
| `railway` | Railway PostgreSQL | Railway MinIO | Single-platform |
| `railway-neon` | Neon PostgreSQL | Railway MinIO | Hybrid (DB branching) |

## Common Operations

### Deploy from a specific branch

```bash
git checkout main && git pull
railway up --detach
```

### Update environment variables

```bash
# Set variables (triggers automatic redeploy)
railway variables set ANTHROPIC_API_KEY=sk-ant-xxx
railway variables set ADMIN_API_KEY=new-key
```

### Check deployment health

```bash
# Using the verify-deployment script
API_URL=https://your-backend.up.railway.app \
  bash skills/aca-deployment/scripts/verify-deployment.sh

# Or manually
curl https://your-backend.up.railway.app/health
curl https://your-backend.up.railway.app/ready
```

### View recent errors

```bash
railway logs --service backend 2>&1 | grep -i error | tail -20
```

## Troubleshooting

### PORT is dynamic

Railway injects `PORT` at runtime. The Dockerfile must use shell form:

```dockerfile
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Never hardcode the port.

### Connection limits (Hobby plan)

Railway Hobby plan has limited connections. Use conservative pool settings:

```yaml
# In profile settings
railway_pool_size: 3
railway_max_overflow: 2
```

Exceeding this causes `QueuePool limit reached` errors.

### MinIO auto-discovery

Railway MinIO needs either `RAILWAY_PUBLIC_DOMAIN` or explicit `RAILWAY_MINIO_ENDPOINT`. Without it, the storage provider can't construct URLs.

### Slow builds (custom image)

The custom Docker image with Rust extensions (pg_search, pgvector) takes ~20 minutes to build. Use the GHCR pre-built image to skip compilation:

```yaml
# In railway.json or Railway dashboard
image: ghcr.io/your-org/newsletter-aggregator:latest
```

### Volumes not persistent by default

Railway containers are ephemeral. Attach a volume in the Railway dashboard for persistent data (e.g., local file uploads).

### CORS in production

When `ENVIRONMENT=production`, `ALLOWED_ORIGINS` must be explicitly set. Dev defaults (localhost) produce an empty CORS list in production:

```bash
railway variables set ALLOWED_ORIGINS=https://your-frontend.up.railway.app
```

### Extension version pinning

Pin extension versions in the Dockerfile to prevent breakage:

```dockerfile
RUN git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
```

Unpinned builds break when upstream changes pgrx versions.
