# Implementation Tasks

## 1. Railway Docker Image (PG17)

- [ ] 1.1 Update `railway/postgres/Dockerfile`:
  - Base images: `postgres:16-bookworm` → `postgres:17-bookworm`
  - Build deps: `postgresql-server-dev-16` → `postgresql-server-dev-17`
  - pgrx init: `--pg16` → `--pg17`
  - pgvector: `--branch v0.7.4` → `--branch v0.8.0`
  - pg_search: remove `--no-default-features --features pg16`
  - Extension paths: `postgresql/16/` → `postgresql/17/`
- [ ] 1.2 Update `railway/postgres/postgresql.conf`:
  - `shared_preload_libraries = 'pg_cron,pg_search'` → `shared_preload_libraries = 'pg_cron'`
  - Update PG16 comment to PG17
- [ ] 1.3 Build and test Docker image locally:
  - Verify all 4 extensions load (`CREATE EXTENSION`)
  - Functional test: vector distance, cron listing, pgmq queue ops
- [ ] 1.4 Update `railway/postgres/README.md`: image tag `16-railway` → `17-railway`

## 2. Local Development (docker-compose)

- [ ] 2.1 Update `docker-compose.yml`: `postgres:15` → `postgres:17`
- [ ] 2.2 Verify `alembic upgrade head` works against PG17

## 3. CI Pipeline

- [ ] 3.1 Update `.github/workflows/ci.yml`: service image `postgres:16` → `postgres:17`
- [ ] 3.2 Verify CI tests pass against PG17

## 4. Documentation

- [ ] 4.1 Update `docs/SETUP.md`: all image tag references `16-railway` → `17-railway`
- [ ] 4.2 Update `openspec/project.md`: PostgreSQL version reference
- [ ] 4.3 Add PG17 migration notes to `docs/SETUP.md` (local dev: `docker compose down -v`)

## 5. Verification

- [ ] 5.1 Run full test suite (`pytest`) against PG17 CI image
- [ ] 5.2 Verify Railway Docker image starts and all extensions functional
- [ ] 5.3 Confirm GHCR image tag updated in Railway deployment docs
