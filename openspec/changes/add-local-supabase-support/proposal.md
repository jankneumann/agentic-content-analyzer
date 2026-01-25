# Change: Add Local Supabase Development Support

## Why

Currently, developing with Supabase features requires a cloud connection:
- Storage testing requires cloud Supabase Storage bucket
- Database testing may hit cloud instance
- No offline development capability
- CI/CD tests depend on cloud availability

Supabase provides a full local development stack via Docker that includes:
- PostgreSQL database (port 54322)
- PostgREST API (port 54321)
- S3-compatible Storage (port 54321/storage/v1)
- Auth, Edge Functions, and more

Adding local Supabase support enables:
- **Dev/Prod Parity**: Same APIs locally as in production
- **Offline Development**: No cloud dependency during coding
- **CI/CD Testing**: Run integration tests against real Supabase APIs
- **Cost Savings**: No cloud usage during development
- **Schema Sync**: Bidirectional migration sync with `supabase db push/pull`

## What Changes

- **NEW**: `SUPABASE_LOCAL=true` convenience setting
- **NEW**: Auto-configured local endpoints when local mode enabled
- **NEW**: Docker Compose profile for local Supabase
- **NEW**: Schema sync workflow documentation
- **MODIFIED**: Settings to support local/cloud Supabase switching
- **NEW**: Supabase CLI integration guidance

## Impact

- **Affected specs**: Adds to `local-development` capability
- **Affected code**:
  - `src/config/settings.py` - Add local Supabase settings
  - `docker-compose.yml` - Add Supabase services (optional profile)
  - `docs/SETUP.md` - Local Supabase setup instructions
- **Dependencies**: None (enhances existing Supabase support)
- **Breaking changes**: None
