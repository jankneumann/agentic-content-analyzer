# Design — Database Source Overrides

## Context

Source resolution today funnels through `load_sources_config()` in `src/config/sources.py`. Consumers (`blog_scraper`, `orchestrator`, `pipeline/runner`, `mcp_server`, `settings.get_sources_config()`) call it directly, mostly with no arguments. The model-override mechanism (`settings_overrides` table → `SettingsService` → `model_settings_routes.py`) is the template to mirror, with one difference: a source override is a structured object, not a scalar, so it is validated through the existing `Source` discriminated union.

## Decisions

### D1 — Dedicated `source_overrides` table (not `settings_overrides`)
Structured columns enable type-aware queries and column constraints. Mirrors the `settings_overrides` migration idempotency pattern.

Columns: `id` PK; `source_key` (String, unique, indexed) = `<type>:<locator>`; `source_type` (String, indexed); `config` (JSON/JSONB) full validated source dict; `enabled` (Boolean, default true); `version` (Integer, default 1, bumped on update); `description` (Text, nullable); `created_at`/`updated_at` (DateTime). `config` is stored as a JSON column (portable across Postgres/SQLite used in tests).

### D2 — Natural key `<type>:<locator>`
Locator per type: `url` (blog, rss, substack, podcast, youtube_rss), `id` (youtube_playlist), `channel_id` (youtube_channel), `query` (gmail, scholar). A `_source_key(source_dict)` helper in `src/config/sources.py` is the single source of truth for key derivation and is reused by the loader merge, the service, and the existing `source_routes` overview so YAML and DB sources line up. arxiv/huggingface_papers/websearch/readwise use a stable locator too (e.g. `name` or a type-specific field); the helper raises on an unkeyable source so callers fail loudly.

### D3 — Merge inside `load_sources_config()`, fail open
After building the YAML `SourcesConfig`, look up DB overrides via a lazily-imported `SourceOverrideService` wrapped in try/except (same shape as `_get_db_model_override`). Build a dict keyed by `source_key`: start from YAML sources, then for each DB override replace/add by key; a DB override with `enabled:false` removes the key from the merged map (shadow). Re-validate merged dicts through `SourcesConfig`. Attach `origin` via a non-persisted attribute or a parallel map returned to API/CLI (the `Source` Pydantic models get an `origin: Literal["yaml","db"] = "yaml"` field defaulting to yaml; merge sets `db`). On any DB error, return YAML-only config and debug-log.

**Caching note**: `load_sources_config()` is currently un-cached and called per-ingest; adding a DB read per call is acceptable (ingest is not hot-loop). No new cache is introduced to avoid staleness after edits.

### D4 — Validation on write through the source union
`SourceOverrideService.upsert(config: dict)` runs `SourcesConfig(sources=[config])` (or `TypeAdapter(Source)`) to validate before persisting, raising a `ValueError` mapped to HTTP 400. This reuses the exact schema the YAML loader enforces — no second schema.

### D5 — Disable-shadow for YAML sources
Disabling a YAML source creates/updates a `source_overrides` row with the YAML source's key, its `config` copied from the resolved YAML source (so the row is self-describing), and `enabled:false`. Enabling later flips the flag. Hard delete removes the row entirely (DB-origin) or, for a shadow over a YAML source, reverts to YAML by deleting the shadow.

### D6 — API: extend `/api/v1/sources`
Keep the existing read-only `GET /api/v1/sources` overview backward-compatible (add `origin` to `SourceInfo`). Add write routes in a new `src/api/source_write_routes.py` mounted under the same prefix, all `Depends(verify_admin_key)`: `POST /api/v1/sources` (add/update), `DELETE /api/v1/sources/{key}`, `POST /api/v1/sources/{key}/enable`, `POST /api/v1/sources/{key}/disable`. Key is path-escaped (URL locator contains slashes → use `{key:path}` or base64).

### D7 — CLI dual-mode mirrors `settings_commands.py`
New `src/cli/source_commands.py` with `is_direct_mode()` / `httpx.ConnectError` fallback and `guard_remote_backend`. New `ApiClient` methods in `src/cli/api_client.py`. Registered as the `sources` Typer sub-app in the CLI entrypoint.

### D8 — Web `/settings/sources` mirrors `ModelConfigurator`
New route `web/src/routes/settings/sources.tsx`, component `SourcesConfigurator.tsx`, API module `web/src/lib/api/sources.ts`, hooks in `use-settings.ts`, types in `types/settings.ts`, query keys, and a tab entry in `routes/settings.tsx` + nav. React Query for fetch/mutate with invalidation; shadcn/ui + sonner toasts; add-source dialog renders a per-type field form driven by the selected source type.

## Risks / Trade-offs
- **Key collisions / unkeyable types**: mitigated by a single `_source_key` helper that raises on unkeyable sources.
- **Origin field on Pydantic models**: adding `origin` to `SourceBase` is low-risk (defaulted) and ignored by ingestion logic.
- **Path-escaping the natural key in URLs**: URLs as keys contain `:` and `/`; use `{key:path}` plus query-param fallback, covered by a contract test.
