# Tasks: Use ParadeDB on Railway and Langfuse as Default Observability

**Change ID**: `use-paradedb-railway-langfuse-default`
**Selected Approach**: A — Config-First, Then Infrastructure

**Non-goals**:
- Database data migration from vanilla Railway PG to ParadeDB (operator responsibility — documented in task 2.3)
- GitHub Actions CI/CD for GHCR image rebuilds (deferred to follow-up proposal)
- Auto-starting Langfuse stack from `make dev` (would break existing workflows)

## Phase 1: Langfuse Default Observability

### Tests First

- [ ] 1.1 Write profile loading tests for Langfuse defaults
  **Spec scenarios**: profile-configuration — Base profile defaults to Langfuse, Local profile uses self-hosted Langfuse, Railway profile uses Langfuse Cloud, Graceful degradation when credentials missing, Profiles with explicit observability override are unaffected
  **Design decisions**: D1 (Cloud for Railway, self-hosted for local), D3 (merge into local.yaml)
  **Dependencies**: None
  **Files**: `tests/test_config/test_langfuse_profile_defaults.py`
  **Details**:
  - **TestProfileLoadingDefaults**: Assert `Settings.observability_provider == "langfuse"` when loading base.yaml, local.yaml, railway.yaml, railway-neon.yaml, staging.yaml, railway-neon-staging.yaml, supabase-cloud.yaml
  - **TestSelfHostedConfig**: Assert local.yaml loads with `langfuse_base_url == "http://localhost:3100"`
  - **TestCloudConfig**: Assert railway.yaml loads with `langfuse_public_key` and `langfuse_secret_key` references
  - **TestGracefulDegradation**: With missing credentials (public_key=None, secret_key=None), assert exactly 1 WARNING log, assert application does not raise, assert provider initializes without error
  - **TestPartialCredentials**: With public_key set but secret_key=None, assert WARNING log about partial auth
  - **TestObservabilityOverride**: Load local.yaml with env `OBSERVABILITY_PROVIDER=braintrust`, assert `Settings.observability_provider == "braintrust"`
  - **TestUnchangedProfiles**: Load ci-neon.yaml, local-opik.yaml, local-supabase.yaml — assert each keeps its explicit observability provider (noop, opik, noop respectively)

### Implementation

- [ ] 1.2 Update `profiles/base.yaml` — change observability default to `langfuse`
  **Spec scenarios**: profile-configuration — Base profile defaults to Langfuse
  **Dependencies**: 1.1
  **Files**: `profiles/base.yaml`
  **Details**:
  - Change `providers.observability: noop` to `providers.observability: langfuse`
  - Set `settings.observability.otel_enabled: true`
  - Keep `settings.observability.otel_service_name: newsletter-aggregator`

- [ ] 1.3 Update `profiles/local.yaml` — add self-hosted Langfuse config
  **Spec scenarios**: profile-configuration — Local profile uses self-hosted Langfuse, Local Langfuse stack not running
  **Design decisions**: D3 (merge self-hosted config into local.yaml)
  **Dependencies**: 1.2
  **Files**: `profiles/local.yaml`
  **Details**:
  - Change `providers.observability: noop` to `providers.observability: langfuse`
  - Add `settings.observability` section with:
    - `otel_enabled: true`
    - `otel_service_name: newsletter-aggregator`
    - `langfuse_base_url: "http://localhost:3100"`
  - Add YAML comments: "# Requires Langfuse stack: make langfuse-up (or docker compose -f docker-compose.langfuse.yml -p langfuse up -d)"
  - Add YAML comment: "# If Langfuse stack is not running, traces are silently dropped (noop-equivalent)"
  - **Note**: This is a BEHAVIOR CHANGE for existing `PROFILE=local` users. Previously no tracing; now Langfuse tracing (with graceful fallback). Users who explicitly want no tracing should set `OBSERVABILITY_PROVIDER=noop`.

- [ ] 1.4 Update `profiles/railway.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Railway profile uses Langfuse Cloud, Railway profile documents ParadeDB GHCR image
  **Design decisions**: D1 (Langfuse Cloud for Railway), D4 (keep Braintrust as option)
  **Dependencies**: 1.2
  **Files**: `profiles/railway.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace `settings.observability` section:
    - Remove `braintrust_api_key`, `braintrust_project_name`
    - Add `langfuse_public_key: "${LANGFUSE_PUBLIC_KEY}"`
    - Add `langfuse_secret_key: "${LANGFUSE_SECRET_KEY}"`
    - Keep `otel_enabled: true` and `otel_service_name: newsletter-aggregator`
    - Remove `otel_exporter_otlp_endpoint` (Langfuse provider auto-derives it from base_url)
  - Update required secrets comment in file header: replace `BRAINTRUST_API_KEY` with `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
  - Add comment: "# Override to Braintrust: set OBSERVABILITY_PROVIDER=braintrust and BRAINTRUST_API_KEY"

- [ ] 1.5 Update `profiles/railway-neon.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Railway-Neon profile uses Langfuse Cloud
  **Dependencies**: 1.2
  **Files**: `profiles/railway-neon.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section with Langfuse Cloud config (same pattern as 1.4)
  - Update required secrets comment in file header

- [ ] 1.6 Update `profiles/staging.yaml` — switch to Langfuse Cloud with staging isolation
  **Spec scenarios**: profile-configuration — Staging profile uses Langfuse Cloud with staging project isolation, Staging profile with all credential variables unset
  **Dependencies**: 1.2
  **Files**: `profiles/staging.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section:
    - `langfuse_public_key: "${STAGING_LANGFUSE_PUBLIC_KEY:-${LANGFUSE_PUBLIC_KEY:-}}"`
    - `langfuse_secret_key: "${STAGING_LANGFUSE_SECRET_KEY:-${LANGFUSE_SECRET_KEY:-}}"`
    - `otel_service_name: "newsletter-aggregator-staging"`
    - Remove Braintrust settings
  - Note: when both STAGING_ and base keys are unset, interpolation resolves to empty string — triggers graceful degradation (warning + noop)

- [ ] 1.7 Update `profiles/railway-neon-staging.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Railway-Neon-Staging profile uses Langfuse Cloud
  **Dependencies**: 1.2
  **Files**: `profiles/railway-neon-staging.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section with staging Langfuse Cloud config (same pattern as 1.6)

- [ ] 1.8 Update `profiles/supabase-cloud.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Supabase-Cloud profile uses Langfuse Cloud
  **Dependencies**: 1.2
  **Files**: `profiles/supabase-cloud.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section with Langfuse Cloud config (same pattern as 1.4)

- [ ] 1.9 Verify `.secrets.yaml` template has Langfuse credential placeholders
  **Dependencies**: 1.2
  **Files**: `.secrets.yaml.example` (if it exists)
  **Details**:
  - Verify `base.yaml` already has `langfuse_public_key: "${LANGFUSE_PUBLIC_KEY:-}"` and `langfuse_secret_key: "${LANGFUSE_SECRET_KEY:-}"` in `api_keys` section (already present)
  - If `.secrets.yaml.example` exists, ensure it contains `LANGFUSE_PUBLIC_KEY:` and `LANGFUSE_SECRET_KEY:` placeholders
  - If `.secrets.yaml.example` does not exist, skip (credentials are documented in profile comments and docs)
  - **This is a verification-only task** — no file creation

- [ ] 1.10 Update Makefile comments for default Langfuse dev experience
  **Dependencies**: 1.3
  **Files**: `Makefile`
  **Details**:
  - Add comment to `make dev` target: "# Note: Langfuse is the default observability provider. Start Langfuse first: make langfuse-up"
  - Add comment to `make dev-langfuse` target: "# Equivalent to 'make dev' since Langfuse is now the default. Kept for backward compatibility."
  - Do NOT make `langfuse-up` a prerequisite of `make dev` (would break existing workflows for users who don't want Langfuse overhead)
  - **Design rationale (D5)**: Keep `make dev` unchanged to avoid breaking existing workflows. Langfuse graceful fallback handles the case where the stack isn't running.

- [ ] 1.11 Update documentation for Langfuse default
  **Dependencies**: 1.4, 1.5, 1.6
  **Files**: `docs/SETUP.md`, `docs/PROFILES.md`
  **Details**:
  - In `docs/SETUP.md`:
    - Update Observability provider table: change default from `noop` to `langfuse`
    - Update Railway deployment section: replace `BRAINTRUST_API_KEY` requirement with `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
    - Add subsection "Langfuse Setup" under Observability: self-hosted flow (`make langfuse-up`, get keys from localhost:3100 Settings > API Keys) vs Cloud flow (get keys from cloud.langfuse.com)
    - Add note: "To use Braintrust instead, set `OBSERVABILITY_PROVIDER=braintrust` and `BRAINTRUST_API_KEY`"
  - In `docs/PROFILES.md`:
    - Update profile comparison table: change observability column from `noop`/`braintrust` to `langfuse`
    - Add note about `PROFILE=local` behavior change (now includes Langfuse tracing with graceful fallback)

## Phase 2: ParadeDB on Railway

- [ ] 2.1 MANUAL: Build and publish ParadeDB image to GHCR
  **Design decisions**: D2 (GHCR pre-built image)
  **Dependencies**: Phase 1 complete
  **Files**: `railway/postgres/Dockerfile` (read-only — not modified)
  **Details**:
  - **This is a manual operator step**, not an automated task
  - Authenticate: `echo $GHCR_PAT | docker login ghcr.io -u jankneumann --password-stdin`
  - Build: `docker build -t ghcr.io/jankneumann/aca-postgres:17-railway ./railway/postgres/`
  - Verify locally: `docker run --rm -d --name paradedb-test -e POSTGRES_PASSWORD=test ghcr.io/jankneumann/aca-postgres:17-railway` then check extensions: `docker exec paradedb-test psql -U postgres -c "SELECT extname FROM pg_extension;"`
  - Push: `docker push ghcr.io/jankneumann/aca-postgres:17-railway`
  - Verify pullable: `docker pull ghcr.io/jankneumann/aca-postgres:17-railway`
  - Clean up: `docker stop paradedb-test`

- [ ] 2.2 Update Railway deployment documentation
  **Spec scenarios**: profile-configuration — Railway profile documents ParadeDB GHCR image
  **Dependencies**: 2.1
  **Files**: `docs/MOBILE_DEPLOYMENT.md`, `railway/postgres/README.md`
  **Details**:
  - In `railway/postgres/README.md`, add section "Deploying to Railway":
    - GHCR image URL: `ghcr.io/jankneumann/aca-postgres:17-railway`
    - Railway Docker service setup steps
    - Environment variables: `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_USER`
    - Pre-installed extensions: pgvector, pg_search, pgmq, pg_cron
    - GHCR image rebuild steps (for future Dockerfile updates)
  - In `docs/MOBILE_DEPLOYMENT.md`:
    - Add link to `railway/postgres/README.md` in Database section
    - Note: ParadeDB GHCR image replaces vanilla Railway PostgreSQL
  - Document data migration path (operator responsibility, not automated):
    - `pg_dump --format=custom` from vanilla Railway PG
    - Deploy ParadeDB GHCR image as new Railway service
    - `pg_restore --no-owner --no-privileges` into ParadeDB
    - Validate: `SELECT count(*) FROM <key tables>`

- [ ] 2.3 Add ParadeDB GHCR image comments to Railway profile
  **Spec scenarios**: profile-configuration — Railway profile documents ParadeDB GHCR image
  **Dependencies**: 2.1
  **Files**: `profiles/railway.yaml`
  **Details**:
  - Add YAML comments in file header documenting:
    - Railway database uses ParadeDB GHCR image: `ghcr.io/jankneumann/aca-postgres:17-railway`
    - Pre-installed extensions: pgvector, pg_search, pgmq, pg_cron
    - See `railway/postgres/README.md` for deployment instructions

## Phase 3: Validation and Cleanup

- [ ] 3.1 Run full profile validation
  **Dependencies**: 2.3
  **Files**: None (validation only)
  **Details** — specific pass/fail criteria:
  - `aca profile validate base` exits 0
  - `aca profile validate local` exits 0
  - `aca profile validate railway` exits 0
  - `aca profile validate railway-neon` exits 0
  - `aca profile validate railway-neon-staging` exits 0
  - `aca profile validate staging` exits 0
  - `aca profile validate supabase-cloud` exits 0
  - `aca profile show base` outputs `observability: langfuse`
  - `aca profile show local` outputs `langfuse_base_url: http://localhost:3100`
  - `aca profile show railway` outputs `langfuse_public_key: ${LANGFUSE_PUBLIC_KEY}`
  - Unchanged profiles: `aca profile validate ci-neon` exits 0, `aca profile validate local-opik` exits 0
  - Run existing profile tests: `pytest tests/test_config/ -v`

- [ ] 3.2 Add deprecation comment to `local-langfuse.yaml`
  **Dependencies**: 1.3
  **Files**: `profiles/local-langfuse.yaml`
  **Details**:
  - Add comment at top: "# DEPRECATED: This profile is now equivalent to local.yaml (Langfuse is the default). Kept for backward compatibility with scripts using PROFILE=local-langfuse."
  - Keep file unchanged otherwise — no functional modification

- [ ] 3.3 Update CLAUDE.md infrastructure topology
  **Dependencies**: 3.1
  **Files**: `CLAUDE.md`
  **Details**:
  - Update the Observability line in the Providers table: change `noop` default mention to `langfuse`
  - Verify the Configuration section accurately reflects new defaults
