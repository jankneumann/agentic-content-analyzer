# Tasks: Use ParadeDB on Railway and Langfuse as Default Observability

**Change ID**: `use-paradedb-railway-langfuse-default`
**Selected Approach**: A — Config-First, Then Infrastructure

## Phase 1: Langfuse Default Observability

### Tests First

- [ ] 1.1 Write profile loading tests for Langfuse defaults
  **Spec scenarios**: profile-configuration — Base profile defaults to Langfuse, Graceful degradation when credentials missing
  **Design decisions**: D1 (Cloud for Railway, self-hosted for local), D3 (merge into local.yaml)
  **Dependencies**: None
  **Files**: `tests/test_config/test_profile_loading.py` (or equivalent)
  **Details**:
  - Test that `base.yaml` loads with `observability: langfuse` and `otel_enabled: true`
  - Test that `local.yaml` loads with `langfuse_base_url: http://localhost:3100`
  - Test that `railway.yaml` loads with `langfuse` provider and cloud base URL
  - Test that `railway-neon.yaml` loads with `langfuse` provider
  - Test that `staging.yaml` loads with `langfuse` provider and staging key references
  - Test that missing Langfuse credentials produce warnings, not errors
  - Test that `OBSERVABILITY_PROVIDER=braintrust` override still works

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
  **Spec scenarios**: profile-configuration — Local profile uses self-hosted Langfuse
  **Design decisions**: D3 (merge self-hosted config into local.yaml)
  **Dependencies**: 1.2
  **Files**: `profiles/local.yaml`
  **Details**:
  - Change `providers.observability: noop` to `providers.observability: langfuse`
  - Add `settings.observability` section with:
    - `otel_enabled: true`
    - `otel_service_name: newsletter-aggregator`
    - `langfuse_base_url: "http://localhost:3100"`
  - Add YAML comments explaining Langfuse stack requirement (`make langfuse-up`)
  - Add comment about graceful fallback if Langfuse isn't running

- [ ] 1.4 Update `profiles/railway.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Railway profile uses Langfuse Cloud
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
  - Add comment: "Override to Braintrust: set OBSERVABILITY_PROVIDER=braintrust and BRAINTRUST_API_KEY"

- [ ] 1.5 Update `profiles/railway-neon.yaml` — switch to Langfuse Cloud
  **Spec scenarios**: profile-configuration — Railway-Neon profile uses Langfuse Cloud
  **Dependencies**: 1.2
  **Files**: `profiles/railway-neon.yaml`
  **Details**:
  - Same observability changes as 1.4 (railway.yaml)
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section with Langfuse Cloud config
  - Update required secrets comment in file header

- [ ] 1.6 Update `profiles/staging.yaml` — switch to Langfuse Cloud with staging isolation
  **Spec scenarios**: profile-configuration — Staging profile uses Langfuse Cloud with staging project isolation
  **Dependencies**: 1.2
  **Files**: `profiles/staging.yaml`
  **Details**:
  - Change `providers.observability: braintrust` to `providers.observability: langfuse`
  - Replace observability section:
    - `langfuse_public_key: "${STAGING_LANGFUSE_PUBLIC_KEY:-${LANGFUSE_PUBLIC_KEY:-}}"`
    - `langfuse_secret_key: "${STAGING_LANGFUSE_SECRET_KEY:-${LANGFUSE_SECRET_KEY:-}}"`
    - `otel_service_name: "newsletter-aggregator-staging"`
    - Remove Braintrust settings

- [ ] 1.7 Update `.secrets.yaml` template and base.yaml API keys
  **Dependencies**: 1.2
  **Files**: `.secrets.yaml.example` (or equivalent template), `profiles/base.yaml`
  **Details**:
  - Ensure `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` placeholders exist in secrets template
  - Verify `base.yaml` already has `langfuse_public_key: "${LANGFUSE_PUBLIC_KEY:-}"` and `langfuse_secret_key: "${LANGFUSE_SECRET_KEY:-}"` in `api_keys` section (already present — verify only)

- [ ] 1.8 Update Makefile for default Langfuse dev experience
  **Dependencies**: 1.3
  **Files**: `Makefile`
  **Details**:
  - Consider adding `langfuse-up` as a dependency of the `dev` target, or document the two-step startup
  - Ensure `make dev-langfuse` still works (may become equivalent to `make dev`)
  - Add comment in `make dev` target about Langfuse being the default

- [ ] 1.9 Update documentation for Langfuse default
  **Dependencies**: 1.4, 1.5, 1.6
  **Files**: `docs/SETUP.md`, `docs/PROFILES.md`
  **Details**:
  - Update observability provider table: mark Langfuse as default, Braintrust as available override
  - Document credential setup for both self-hosted (local) and cloud (Railway)
  - Add first-time setup section for self-hosted Langfuse (create account, get API keys)
  - Update Railway deployment section: replace Braintrust key requirement with Langfuse keys

## Phase 2: ParadeDB on Railway

- [ ] 2.1 Write verification test for ParadeDB GHCR image
  **Spec scenarios**: profile-configuration — Railway profile documents ParadeDB GHCR image
  **Design decisions**: D2 (GHCR pre-built image)
  **Dependencies**: Phase 1 complete
  **Files**: `tests/integration/test_railway_paradedb.py` (or shell script)
  **Details**:
  - Test that the GHCR image can be pulled and started
  - Test that pg_search, pgvector, pgmq, pg_cron extensions are available
  - Test that BM25 search strategy auto-detects ParadeDB
  - This may be a manual verification step rather than automated test

- [ ] 2.2 Build and publish ParadeDB image to GHCR
  **Design decisions**: D2 (GHCR pre-built image)
  **Dependencies**: 2.1
  **Files**: `railway/postgres/Dockerfile`
  **Details**:
  - Build from existing `railway/postgres/Dockerfile`
  - Tag as `ghcr.io/jankneumann/aca-postgres:17-railway`
  - Push to GHCR (requires PAT with `write:packages` scope)
  - Verify image is pullable: `docker pull ghcr.io/jankneumann/aca-postgres:17-railway`
  - **This is a manual step** — operator executes on their machine

- [ ] 2.3 Update Railway deployment documentation
  **Dependencies**: 2.2
  **Files**: `docs/MOBILE_DEPLOYMENT.md`, `railway/postgres/README.md`
  **Details**:
  - Document how to deploy ParadeDB GHCR image as a Railway Docker service
  - Document environment variables for the PostgreSQL service
  - Document the data migration path: `pg_dump` from vanilla Railway PG, `pg_restore` into ParadeDB service
  - Add GHCR publish workflow steps (for future image updates)
  - Update Railway profile comments in `railway.yaml` to reference GHCR image

- [ ] 2.4 Add ParadeDB GHCR image comments to Railway profile
  **Spec scenarios**: profile-configuration — Railway profile documents ParadeDB GHCR image
  **Dependencies**: 2.2
  **Files**: `profiles/railway.yaml`
  **Details**:
  - Add YAML comments documenting that Railway database should use the ParadeDB GHCR image
  - List pre-installed extensions: pgvector, pg_search, pgmq, pg_cron
  - Reference `railway/postgres/README.md` for deployment instructions

## Phase 3: Validation and Cleanup

- [ ] 3.1 Run full profile validation
  **Dependencies**: 2.4
  **Files**: None (validation only)
  **Details**:
  - Run `aca profile validate` for all modified profiles
  - Verify all profiles load correctly with `aca profile show <name>`
  - Run existing test suite to check for regressions

- [ ] 3.2 Evaluate `local-langfuse.yaml` profile
  **Dependencies**: 1.3
  **Files**: `profiles/local-langfuse.yaml`
  **Details**:
  - Since `local.yaml` now includes Langfuse self-hosted config, `local-langfuse.yaml` is redundant
  - Keep the file for backward compatibility (users may have `PROFILE=local-langfuse` in scripts)
  - Add a comment: "This profile is equivalent to local.yaml — kept for backward compatibility"

- [ ] 3.3 Update CLAUDE.md infrastructure topology
  **Dependencies**: 3.1
  **Files**: `CLAUDE.md`
  **Details**:
  - Update the observability provider line in the Configuration section
  - Verify the Providers table shows Langfuse as default
