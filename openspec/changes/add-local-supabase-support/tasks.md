# Tasks: Local Supabase Development Support

## Phase 1: Settings Configuration

- [ ] 1.1 Add `supabase_local: bool = False` to settings
- [ ] 1.2 Add local endpoint defaults when `supabase_local=True`:
  - `supabase_url` → `http://127.0.0.1:54321`
  - `supabase_db_url` → `postgresql://postgres:postgres@127.0.0.1:54322/postgres`
  - `supabase_anon_key` → Local dev key (from `supabase status`)
  - `supabase_service_role_key` → Local dev key
- [ ] 1.3 Auto-detect local Supabase from environment
- [ ] 1.4 Add settings validation (warn if mixing local/cloud)

## Phase 2: Docker Compose Integration

- [ ] 2.1 Add `supabase` profile to docker-compose.yml
- [ ] 2.2 Configure Supabase services:
  - `supabase-db` (PostgreSQL)
  - `supabase-api` (PostgREST + GoTrue + Storage)
  - `supabase-studio` (Admin UI on port 54323)
- [ ] 2.3 Add volume mounts for data persistence
- [ ] 2.4 Configure networking between services
- [ ] 2.5 Add health checks for Supabase services

## Phase 3: Storage Provider Updates

- [ ] 3.1 Update `SupabaseFileStorage` to detect local mode
- [ ] 3.2 Use local S3 endpoint when `supabase_local=True`
- [ ] 3.3 Handle local bucket creation (no dashboard needed)
- [ ] 3.4 Test storage operations against local instance

## Phase 4: Database Provider Updates

- [ ] 4.1 Ensure database provider works with local Supabase
- [ ] 4.2 Document connection string format for local
- [ ] 4.3 Test migrations against local Supabase

## Phase 5: Supabase CLI Integration

- [ ] 5.1 Document `supabase init` for project setup
- [ ] 5.2 Document `supabase start` / `supabase stop`
- [ ] 5.3 Add schema sync workflow:
  - `supabase db diff` - Generate migration from changes
  - `supabase db push` - Apply local changes to cloud
  - `supabase db pull` - Pull cloud schema locally
- [ ] 5.4 Add `supabase/migrations/` to project structure
- [ ] 5.5 Document `supabase link` for cloud project connection

## Phase 6: Testing

- [ ] 6.1 Add integration test for local Supabase storage
- [ ] 6.2 Add integration test for local Supabase database
- [ ] 6.3 Add CI workflow for local Supabase tests
- [ ] 6.4 Test schema sync workflow

## Phase 7: Documentation

- [ ] 7.1 Add "Local Supabase Setup" section to docs/SETUP.md
- [ ] 7.2 Document environment switching (local ↔ cloud)
- [ ] 7.3 Add troubleshooting section for common issues
- [ ] 7.4 Update CLAUDE.md with local Supabase guidance
- [ ] 7.5 Add schema migration workflow guide
