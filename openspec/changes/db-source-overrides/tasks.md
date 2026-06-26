# Tasks — db-source-overrides

Task ordering is test-first (RED before GREEN). Sizes per the Task Sizing Reference.

## Phase 0 — Contracts (wp-contracts)

- [x] 0.1 Validate `contracts/db/schema.sql` and `contracts/openapi/v1.yaml` parse and align with the spec deltas. **(XS)**
  **Spec scenarios**: source-configuration (Database Source Overrides, Source Override Management API)
  **Dependencies**: None

## Phase 1 — Backend core: key helper, model, migration, service (wp-backend-core)

- [x] 1.1 Write tests for `_source_key()` natural-key derivation across all source types (blog/rss/substack/podcast/youtube_rss → url; youtube_playlist → id; youtube_channel → channel_id; gmail/scholar → query; unkeyable → raises). **(S)**
  **Spec scenarios**: Natural-Key Source Identity (locator per type)
  **Design decisions**: D2
  **Dependencies**: 0.1
- [x] 1.2 Add `_source_key()` helper and an `origin: Literal["yaml","db"] = "yaml"` field on `SourceBase` in `src/config/sources.py`. **(S)**
  **Dependencies**: 1.1
- [x] 1.3 Write tests for the `SourceOverride` model + migration (idempotent create, unique `source_key`, JSON round-trip). **(S)**
  **Contracts**: contracts/db/schema.sql
  **Dependencies**: 0.1
- [x] 1.4 Create `src/models/source_override.py` and an idempotent Alembic migration for `source_overrides` (mirror `b1c2d3e4f5a6` settings_overrides pattern; run `alembic heads` to avoid multiple heads). **(M)**
  **Contracts**: contracts/db/schema.sql
  **Design decisions**: D1
  **Dependencies**: 1.3
- [x] Checkpoint: run model/migration tests, `alembic upgrade head` on a scratch DB, review diff, verify scope.
- [x] 1.5 Write tests for `SourceOverrideService`: upsert (insert + version-bump update), validation rejection via the source union, list (with type filter), get, delete, enable/disable, disable-shadow config capture. **(M)**
  **Spec scenarios**: Database Source Overrides (all), Source Resolution Precedence (disable/edit)
  **Design decisions**: D4, D5
  **Dependencies**: 1.2, 1.4
- [x] 1.6 Implement `src/services/source_override_service.py` (upsert/list/get/delete/set_enabled), validating `config` through `SourcesConfig`/`TypeAdapter(Source)` before persist. **(M)**
  **Design decisions**: D4, D5
  **Dependencies**: 1.5
- [x] 1.7 Write tests for the `load_sources_config()` merge: DB adds new source (origin db), DB overrides YAML twin by key, DB `enabled:false` shadows YAML source, DB-unavailable falls open to YAML. **(M)**
  **Spec scenarios**: Source Resolution Precedence and Merge (all four scenarios)
  **Design decisions**: D3
  **Dependencies**: 1.6
- [x] 1.8 Implement the DB-override merge inside `load_sources_config()` with lazy import + try/except fail-open and origin tagging. **(M)**
  **Design decisions**: D3
  **Dependencies**: 1.7
- [x] Checkpoint: run backend-core suite, review diff (`src/config/sources.py`, `src/models/`, `src/services/`, `alembic/`), verify scope.

## Phase 2 — Backend API (wp-backend-api)

- [x] 2.1 Write API tests: list returns origin/enabled for YAML+DB; POST upsert (200 + result); invalid config → 400; unauthenticated write → 401; delete → 200/404; enable/disable → persisted. **(M)**
  **Spec scenarios**: Source Override Management API (all)
  **Contracts**: contracts/openapi/v1.yaml
  **Dependencies**: 1.6
- [x] 2.2 Add `origin`/`source_key` to `SourceInfo` in `src/api/source_routes.py` and implement `src/api/source_write_routes.py` (POST/DELETE/enable/disable, `verify_admin_key`, `{key:path}` handling); register the router in `src/api/app.py`. **(M)**
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D6
  **Dependencies**: 2.1
- [x] Checkpoint: run API tests, review diff, verify scope.

## Phase 3 — CLI (wp-cli)

- [x] 3.1 Write CLI tests: `aca sources add/list/remove/enable/disable` in direct mode (DB) and HTTP mode (mocked client), including list origin column. **(M)**
  **Spec scenarios**: Source Override CLI (all)
  **Dependencies**: 1.6
- [x] 3.2 Add `ApiClient` source methods in `src/cli/api_client.py` and implement `src/cli/source_commands.py` (dual-mode like `settings_commands.py`); register the `sources` Typer sub-app. **(M)**
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D7
  **Dependencies**: 3.1, 2.2
- [x] Checkpoint: run CLI tests, manually run `aca sources add blog --url https://www.normaltech.ai/`, review diff, verify scope.

## Phase 4 — Web UI (wp-web)

- [x] 4.1 Write component/e2e tests for `SourcesConfigurator`: list grouped by type with origin/enabled badges; add-source dialog validates + posts; toggle enable/disable; delete shown only for db-origin. **(M)**
  **Spec scenarios**: Source Override Web UI (all)
  **Dependencies**: 2.2
- [x] 4.2 Implement `web/src/lib/api/sources.ts`, types, query-keys, hooks, `web/src/components/settings/SourcesConfigurator.tsx`, route `web/src/routes/settings/sources.tsx`, and the settings tab + nav entry. **(M)**
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D8
  **Dependencies**: 4.1
- [x] Checkpoint: run web tests, review diff, verify scope.

## Phase 5 — Integration (wp-integration)

- [x] 5.1 End-to-end acceptance: add `https://www.normaltech.ai/` as a blog via CLI, assert `load_sources_config().get_blog_sources()` includes it with `origin=db`; add via UI and assert it appears; disable a YAML blog and assert exclusion. **(M)**
  **Spec scenarios**: Source Resolution Precedence (db adds source), Source Override CLI, Source Override Web UI
  **Dependencies**: 2.2, 3.2, 4.2
- [x] 5.2 Run full test suite + `openspec validate db-source-overrides --strict`; update `docs/SETUP.md`/sources docs and CLAUDE.md sources note to mention DB overrides. **(S)**
  **Dependencies**: 5.1
- [x] Checkpoint: full suite green, review cumulative diff against all work_allow scopes.
