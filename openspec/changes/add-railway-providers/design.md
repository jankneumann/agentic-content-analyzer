## Context

Railway is a cloud platform that provides managed infrastructure services including PostgreSQL and MinIO (S3-compatible storage). The project needs to support Railway as a deployment target to enable single-platform deployments.

**Key Railway characteristics:**
- Services communicate via private network (RAILWAY_PRIVATE_DOMAIN)
- External access via TCP proxy (RAILWAY_TCP_PROXY_DOMAIN)
- Environment variables are auto-injected for service connections
- SSL certificates are auto-generated and enforced
- PostgreSQL uses standard port 5432 internally

## Goals / Non-Goals

**Goals:**
- Support Railway PostgreSQL as a database provider
- Support Railway MinIO as a storage provider
- Maintain consistency with existing provider patterns
- Enable zero-config deployment when running on Railway

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
        return False  # Not available on Railway PostgreSQL
```

**Alternatives considered:**
- Reuse LocalPostgresProvider: Rejected because Railway has different SSL and pool requirements
- Reuse NeonProvider: Rejected because Railway doesn't need pooler URL conversion

### Decision 2: Railway Storage Provider Implementation

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

### Decision 3: Environment Variable Strategy

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
railway_database_url: str | None = None
railway_minio_endpoint: str | None = None
railway_minio_bucket: str | None = None
minio_root_user: str | None = None
minio_root_password: str | None = None
```

### Decision 4: Provider Detection Pattern

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
| pg_cron not available on Railway | Return `supports_pg_cron() = False`; use external scheduler |
| Railway cold starts affect connection | Use `pool_pre_ping=True` and appropriate timeouts |

## Migration Plan

1. Add Railway provider code (non-breaking)
2. Add documentation
3. Users opt-in by setting `DATABASE_PROVIDER=railway` and `STORAGE_PROVIDER=railway`

**Rollback**: Simply change provider back to previous setting; no data migration needed.

## Open Questions

1. **Should we support Railway's private networking?** - Initial implementation uses public URLs; private networking can be added later if needed
2. **Should Railway MinIO use internal or public endpoint?** - Default to public for simplicity; document private networking option
3. **Should we add Railway-specific health checks?** - Standard PostgreSQL health check should work; monitor and adjust if needed
