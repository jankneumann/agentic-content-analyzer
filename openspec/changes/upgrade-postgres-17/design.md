## Context
The project runs PostgreSQL across four environments: local Docker Compose (PG15), CI (PG16), Railway custom image (PG16), and cloud providers (Neon/Supabase — both support PG17). This version drift creates subtle behavioral differences and complicates extension builds.

PostgreSQL 17 has been production-stable since September 2024, with v17.7 released December 2025. All three cloud providers support it, and Neon now defaults to PG17 for new projects.

## Goals / Non-Goals
- **Goals**: Align all environments on PG17, simplify Railway Docker build, leverage PG17 performance improvements
- **Non-Goals**: Adopting PG17-only SQL features (JSON_TABLE, MERGE RETURNING) in application code — that can come later

## Decisions

### Extension version bumps
- **pgvector v0.7.4 → v0.8.0**: v0.8.0 is the recommended version for PG17. v0.7.4 may compile but isn't tested against PG17.
- **pg_cron v1.6.4**: Keep as-is. v1.6.4 explicitly supports PG13-17 with the MemoryContextReset compatibility fix.
- **pgmq v1.4.4**: Keep as-is. Pure SQL extension, version-agnostic.
- **pg_search v0.13.0**: Keep version but simplify build flags. v0.13.0 defaults to pg17, so remove `--no-default-features --features pg16`.

### shared_preload_libraries
pg_search v0.13.0 still requires `shared_preload_libraries` on PG17 (the requirement is set by the extension, not the PostgreSQL version). Keep `shared_preload_libraries = 'pg_cron,pg_search'`.

### pgrx version alignment
pg_search v0.13.0 uses `pgrx = "0.12.7"`. The Dockerfile already pins `cargo-pgrx@0.12.7`. For PG17, `cargo pgrx init --pg17` replaces `--pg16`.

### Local development alignment
docker-compose.yml jumps from PG15 directly to PG17. This is a clean break — there's no intermediate PG16 local image. Users must `docker compose down -v && docker compose up -d && alembic upgrade head`.

## Risks / Trade-offs
- **Data loss on upgrade**: PG major versions are not binary-compatible. Existing volumes must be recreated (data loss for local dev) or migrated (dump/restore for Railway production).
  → Mitigation: Document the migration path. Local dev data is disposable. Railway production has backup jobs.
- **pgvector v0.8.0 API changes**: Check if any index options or operators changed.
  → Mitigation: We only use basic vector operations (`<->` distance). No breaking changes in v0.8.0.
- **Supabase local image**: `supabase/postgres:15.1.1.41` in docker-compose.yml. Check if a PG17 equivalent exists.
  → Decision: Leave Supabase local image as-is (it's controlled by Supabase's release cycle, not ours).

## Migration Plan

### Local development
1. `docker compose down -v` (destroy existing volumes)
2. Pull updated images
3. `docker compose up -d`
4. `alembic upgrade head`

### Railway production
1. Take backup via pg_cron job (or manual `pg_dump`)
2. Push new GHCR image (`newsletter-postgres:17-railway`)
3. Update Railway service to use new image
4. Recreate volume and restore from backup
5. Run `alembic upgrade head`

### CI
No migration needed — service containers are ephemeral.

## Open Questions
- None — all providers confirmed PG17 support.
