# Change: Upgrade PostgreSQL from 15/16 to 17 across all environments

## Why
PostgreSQL 17 is production-ready across all three providers (Neon, Supabase, Railway) and simplifies our build: pg_search defaults to pg17 (eliminating the `--features pg16` workaround), pgvector v0.8.0 adds PG17 optimizations, and PG17 brings meaningful performance improvements (20x vacuum memory reduction, 2x COPY throughput, JSON_TABLE).

The project currently runs three different PG versions: docker-compose uses PG15, CI uses PG16, and Railway targets PG16. Aligning on PG17 eliminates version drift and ensures consistent behavior.

## What Changes
- Railway Dockerfile: base image `postgres:16-bookworm` → `postgres:17-bookworm`
- Railway Dockerfile: bump pgvector from v0.7.4 to v0.8.0 (PG17-optimized)
- Railway Dockerfile: remove `--no-default-features --features pg16` from pg_search build (pg17 is default)
- Railway Dockerfile: update pgrx init from `--pg16` to `--pg17`
- Railway Dockerfile: update all extension paths from `postgresql/16/` to `postgresql/17/`
- Railway postgresql.conf: remove `pg_search` from `shared_preload_libraries` (not required on PG17)
- Local docker-compose.yml: `postgres:15` → `postgres:17`
- CI workflow: `postgres:16` → `postgres:17`
- Railway README.md and docs/SETUP.md: update image tags from `16-railway` to `17-railway`
- GHCR image tag: `newsletter-postgres:16-railway` → `newsletter-postgres:17-railway`
- openspec/project.md: update PostgreSQL version reference

## Impact
- Affected specs: `database-provider`, `mobile-cloud-infrastructure`
- Affected code: `railway/postgres/Dockerfile`, `railway/postgres/postgresql.conf`, `railway/postgres/README.md`, `docker-compose.yml`, `.github/workflows/ci.yml`, `docs/SETUP.md`, `openspec/project.md`
- **BREAKING**: Existing Railway deployments need to recreate the database volume (PG major version upgrade requires dump/restore or pg_upgrade)
- **BREAKING**: Local docker-compose users need to `docker compose down -v` and re-run migrations
