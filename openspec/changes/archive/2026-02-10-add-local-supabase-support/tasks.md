# Tasks: Local Supabase Development Support

## Phase 1: Settings Configuration

- [x] 1.1 Add `supabase_local: bool = False` to settings
- [x] 1.2 Add local endpoint defaults when `supabase_local=True`:
  - `supabase_url` → `http://127.0.0.1:54321`
  - `supabase_db_url` → `postgresql://postgres:postgres@127.0.0.1:54322/postgres`
  - `supabase_anon_key` → Local dev key (from `supabase status`)
  - `supabase_service_role_key` → Local dev key
- [x] 1.3 Auto-detect local Supabase from environment
- [x] 1.4 Add settings validation (warn if mixing local/cloud)

## Phase 2: Docker Compose Integration

- [x] 2.1 Add `supabase` profile to docker-compose.yml
- [x] 2.2 Configure Supabase services:
  - `supabase-db` (PostgreSQL)
  - `supabase-kong` (API Gateway)
  - `supabase-storage` (Storage API)
  - `supabase-rest` (PostgREST)
- [x] 2.3 Add volume mounts for data persistence
- [x] 2.4 Configure networking between services
- [x] 2.5 Add health checks for Supabase services

## Phase 3: Storage Provider Updates

- [x] 3.1 Update `SupabaseFileStorage` to detect local mode
- [x] 3.2 Use local S3 endpoint when `supabase_local=True`
- [x] 3.3 Handle local bucket creation (no dashboard needed)
- [x] 3.4 Test storage operations against local instance (requires running local Supabase)

## Phase 4: Database Provider Updates

- [x] 4.1 Ensure database provider works with local Supabase
- [x] 4.2 Document connection string format for local
- [x] 4.3 Test migrations against local Supabase (requires running local Supabase)

## Phase 5: Supabase CLI Integration

- [x] 5.1 Document `supabase init` for project setup
- [x] 5.2 Document `supabase start` / `supabase stop`
- [x] 5.3 Add schema sync workflow:
  - `supabase db diff` - Generate migration from changes
  - `supabase db push` - Apply local changes to cloud
  - `supabase db pull` - Pull cloud schema locally
- [x] 5.4 Add `supabase/` to project structure (with kong.yml)
- [x] 5.5 Document `supabase link` for cloud project connection

## Phase 6: Testing

- [x] 6.1 Add integration test for local Supabase storage
- [x] 6.2 Add integration test for local Supabase database
- [ ] 6.3 Add CI workflow for local Supabase tests (deferred - requires CI changes)
- [x] 6.4 Test schema sync workflow (requires running local Supabase)

## Phase 7: Documentation

- [x] 7.1 Add "Local Supabase Setup" section to docs/SETUP.md
- [x] 7.2 Document environment switching (local ↔ cloud)
- [x] 7.3 Add troubleshooting section for common issues
- [x] 7.4 Update CLAUDE.md with local Supabase guidance
- [x] 7.5 Add schema migration workflow guide

## Migration Notes
Open tasks migrated to beads issue `aca-7eq` (Add CI workflow for local Supabase integration tests) on 2026-02-09.
