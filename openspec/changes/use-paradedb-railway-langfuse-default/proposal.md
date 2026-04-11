# Proposal: Use ParadeDB on Railway and Langfuse as Default Observability

**Change ID**: `use-paradedb-railway-langfuse-default`
**Status**: Proposed
**Created**: 2026-04-11

## Why

Two infrastructure parity gaps undermine the development-to-production experience:

1. **Database extension gap**: Local development uses ParadeDB (`paradedb/paradedb:0.22.2-pg17`) with pgvector, pg_search (BM25), pgmq, and pg_cron pre-installed. Railway production uses vanilla PostgreSQL, which lacks these extensions. This means BM25 full-text search falls back to PostgreSQL native FTS on production — a measurable quality degradation in search ranking. The custom ParadeDB image (`railway/postgres/Dockerfile`) already exists but isn't deployed.

2. **Observability gap**: The default observability provider is `noop` (no tracing). Railway uses Braintrust, but the team's actual observability platform is Langfuse. The Langfuse provider (`src/telemetry/providers/langfuse.py`) is already implemented, and a `local-langfuse.yaml` profile exists, but it's opt-in rather than the default. This means most development happens without tracing, and production traces go to a platform that isn't the team's primary tool.

Both gaps are configuration-level — the code infrastructure is already in place. This proposal closes both gaps by deploying the existing ParadeDB image to Railway and making Langfuse the default observability provider across all profiles.

## What Changes

### ParadeDB on Railway
- Publish the existing custom ParadeDB image (`railway/postgres/Dockerfile`) to GHCR as `ghcr.io/jankneumann/newsletter-postgres:17-railway`
- Update `profiles/railway.yaml` to reference the GHCR image for Railway database deployment
- Ensure `railway_pg_search_enabled: true` is set (already the default) so BM25 auto-detection uses ParadeDB strategy
- Document the GHCR publish workflow and Railway deployment steps

### Langfuse as Default Observability
- Change `profiles/base.yaml` default from `observability: noop` to `observability: langfuse`
- Update `profiles/local.yaml` to use self-hosted Langfuse (merge relevant config from `local-langfuse.yaml`)
- Update `profiles/railway.yaml`, `profiles/railway-neon.yaml`, and `profiles/staging.yaml` from `braintrust` to `langfuse` with Langfuse Cloud configuration
- Include `docker-compose.langfuse.yml` services in the default local development stack (or document the required `docker compose -f ... up` invocation)
- Wire Langfuse Cloud credentials (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`) into `.secrets.yaml` template and Railway environment variable documentation
- Keep Braintrust provider code and docs as a non-default option (override via `OBSERVABILITY_PROVIDER=braintrust`)

### Profile Updates (All Profiles)

| Profile | Database (before -> after) | Observability (before -> after) |
|---------|---------------------------|--------------------------------|
| `base.yaml` | `local` (unchanged) | `noop` -> `langfuse` |
| `local.yaml` | `local` (unchanged) | `noop` -> `langfuse` (self-hosted) |
| `local-langfuse.yaml` | `local` (unchanged) | `langfuse` (unchanged, may merge into local.yaml) |
| `railway.yaml` | `railway` (unchanged) | `braintrust` -> `langfuse` (cloud) |
| `railway-neon.yaml` | `neon` (unchanged) | `braintrust` -> `langfuse` (cloud) |
| `staging.yaml` | `neon` (unchanged) | `braintrust` -> `langfuse` (cloud) |

## What Doesn't Change

- **Database provider code**: `src/storage/providers/railway.py` is unchanged — it already supports ParadeDB extensions
- **Langfuse provider code**: `src/telemetry/providers/langfuse.py` is unchanged — already fully implemented
- **Braintrust provider**: Kept as available option, not removed or deprecated
- **Search strategy code**: `src/services/search_strategy.py` auto-detection already handles ParadeDB
- **Neon/Supabase profiles**: `ci-neon.yaml`, `local-supabase.yaml` are unaffected
- **Application code**: No Python code changes required — this is entirely profile/config/deployment work

## Approaches Considered

### Approach A: Config-First, Then Infrastructure (Recommended)

**Description**: Switch Langfuse defaults across all profiles first (low-risk config change), then publish and deploy the ParadeDB GHCR image to Railway. Having observability in place before the database migration means Langfuse traces can monitor the ParadeDB deployment itself.

**Pros**:
- Langfuse tracing is available to observe the ParadeDB migration
- Config changes are easily reversible (just change YAML values back)
- Can validate Langfuse integration in local dev before touching production
- Smallest blast radius per phase

**Cons**:
- Two deployment cycles instead of one
- Brief period where Railway still uses vanilla PG after Langfuse is live

**Effort**: S (config changes are trivial; GHCR publish is a one-time manual step)

### Approach B: Infrastructure-First, Then Config

**Description**: Deploy ParadeDB GHCR image to Railway first (validates the harder change), then switch observability defaults to Langfuse.

**Pros**:
- Validates the riskier infrastructure change (database) first
- If ParadeDB deployment fails, observability defaults are unaffected
- Database migration can be monitored with existing Braintrust setup

**Cons**:
- Uses Braintrust (not the team's primary tool) to monitor the migration
- Database migration is the higher-risk change — better to have preferred observability first
- If both changes are needed, delaying Langfuse provides no benefit

**Effort**: S

### Approach C: Parallel Implementation

**Description**: Implement both changes simultaneously in parallel work packages. Database config (profiles + GHCR) and observability config (profiles + secrets) are independent provider categories with non-overlapping file scopes, except for shared profile files.

**Pros**:
- Fastest total implementation time
- Changes are genuinely independent at the code level
- Single deployment cycle

**Cons**:
- Profile files (`railway.yaml`, `base.yaml`) are shared — merge conflicts between packages
- If one change fails, harder to isolate which caused the issue
- Debugging two infrastructure changes at once is harder than one at a time

**Effort**: S

### Selected Approach

**Approach A: Config-First, Then Infrastructure** — selected because:
1. Langfuse tracing provides visibility into the ParadeDB deployment
2. Config-only changes (Phase 1) are trivially reversible
3. Phase ordering matches risk gradient: low-risk first, then higher-risk
4. The "two deployment cycles" con is minimal since both phases are small

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Self-hosted Langfuse adds Docker services to local dev | Medium | Document `docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up` pattern; ensure graceful fallback if Langfuse stack isn't running |
| Langfuse Cloud credentials missing on Railway | Low | Validation already warns (not errors) on missing keys; `noop` fallback is implicit |
| ParadeDB GHCR image not available | Medium | Build and verify image before updating profile; document manual build steps |
| Railway ParadeDB data migration | High | New Railway service deployment — data migration via `pg_dump`/`pg_restore` required if replacing existing Railway PG instance |
| Braintrust users lose default access | Low | Keep provider code; document `OBSERVABILITY_PROVIDER=braintrust` override |

## Dependencies

- **Blocked by**: None — all code infrastructure is already implemented
- **Blocks**: No downstream proposals
- **Related**: FalkorDB on Railway (Phase 4 of separate PR), archived `2026-02-28-add-langfuse-observability`, archived `2026-02-06-add-railway-providers`

## Success Criteria

1. `PROFILE=local` with `docker compose up` starts Langfuse and sends traces to self-hosted instance
2. `PROFILE=railway` deploys with ParadeDB GHCR image and Langfuse Cloud — BM25 search uses ParadeDB strategy (not native FTS fallback)
3. All existing profiles load without errors
4. `OBSERVABILITY_PROVIDER=braintrust` override still works on any profile
5. Existing tests pass without modification
