## Why

Ingestion sources live only in `sources.d/*.yaml`, so adding or disabling a source (e.g. a new blog like `https://www.normaltech.ai/`) requires editing a file, committing, and redeploying. The app already solved this exact problem for model selection: per-step model choices are stored as database overrides (`settings_overrides` table) merged on top of YAML defaults with precedence `env > db > yaml`, editable from CLI and the web UI. This change extends that proven override pattern to ingestion sources so non-developers can manage sources at runtime without a git commit.

## What Changes

- **New `source_overrides` database table** storing per-source overrides as validated JSON, keyed by a natural `source_key` (`<type>:<locator>`, e.g. `blog:https://www.normaltech.ai/`).
- **`SourceOverrideService`** with upsert (union-if-new / update-if-existing), list, get, delete, enable/disable — validating each override's `config` against the existing `Source` discriminated union (`BlogSource`/`RSSSource`/…) in `src/config/sources.py` before persisting.
- **Merge DB overrides on top of YAML inside `load_sources_config()`** — the single chokepoint every ingestion consumer (blog scraper, orchestrator, pipeline runner, MCP server, `settings.get_sources_config()`) funnels through. DB entries override their YAML twin by key; a DB entry with `enabled:false` shadows (suppresses) a YAML source. Merge fails open: if the DB is unavailable, YAML-only config is returned. Each merged source carries an `origin` (`yaml` | `db`).
- **Write API endpoints** under `/api/v1/sources` (admin-key protected): list (with origin), add/update, delete, enable/disable. Extends the existing read-only overview router.
- **CLI `aca sources add|list|remove|enable|disable`** with dual-mode HTTP + direct DB access, mirroring `src/cli/settings_commands.py`.
- **Web `/settings/sources` tab** mirroring `ModelConfigurator`: list grouped by type with origin/enabled badges, an add-source dialog (full per-type field set), enable/disable toggle, and delete for db-origin sources.

No breaking changes: YAML remains the default/source-of-truth baseline; DB overrides are additive.

## Capabilities

### New Capabilities
- (none — this extends an existing capability)

### Modified Capabilities
- `source-configuration`: source resolution gains a database-override layer merged over YAML defaults, plus runtime CRUD over sources via API, CLI, and UI. New requirements for natural-key identity, DB-over-YAML precedence, disable-shadowing, fail-open merge, and config validation on write.

## Impact

- **Code**: new `src/models/source_override.py`, `src/services/source_override_service.py`, `src/api/source_write_routes.py` (or extend `src/api/source_routes.py`); modify `src/config/sources.py` (`load_sources_config` merge), `src/cli/source_commands.py` (new), `src/cli/api_client.py` (new methods); web `web/src/routes/settings/sources.tsx`, `web/src/components/settings/SourcesConfigurator.tsx`, `web/src/lib/api/sources.ts`, hooks/types/query-keys, nav tab.
- **Database**: one Alembic migration creating `source_overrides` (idempotent, mirroring the `settings_overrides` migration pattern).
- **APIs**: additive endpoints under `/api/v1/sources`; existing GET overview stays backward-compatible (gains `origin` field).
- **Consumers**: all ingestion paths automatically pick up DB sources because the change is localized to `load_sources_config()`.

## Approaches Considered

### Selected Approach

**Approach A — Dedicated `source_overrides` table + merge in `load_sources_config()`** (approved at Gate 1).

Discovery decisions baked into this approach:
- **Full shadow**: DB overrides may add net-new sources and disable/edit YAML-defined sources (matched by key). A DB row with `enabled:false` suppresses its YAML twin.
- **Natural key**: a source is identified by `<type>:<locator>` (url for blog/rss/podcast/substack, id for youtube_playlist, query for gmail/scholar).
- **Full per-type field set**: CLI/UI expose every field of each source type; the stored `config` is validated against the existing `Source` discriminated union on write.

### Approach A — Dedicated `source_overrides` table + merge in `load_sources_config()` (Recommended)
**Description**: New structured table (`source_key`, `source_type`, `config` JSON, `enabled`, `version`, timestamps, `description`); a dedicated service validates `config` against the source union; `load_sources_config()` overlays DB rows on the YAML list by natural key.
- **Pros**: Clean type-aware queries (list-by-type, enable/disable); config validated through existing Pydantic union; single localized merge point means zero changes to ingestion call sites; natural key auto-aligns DB sources with YAML twins for shadowing.
- **Cons**: One new table + migration; merge must fail open and be cache-aware.
- **Effort**: L (split into M-sized backend/CLI/UI packages).

### Approach B — Reuse the existing `settings_overrides` key/value table
**Description**: Store each source as a JSON blob under a key like `source.blog.<slug>` in the generic key/value table, no new table.
- **Pros**: Maximal symmetry with the model-override mechanism; no migration; reuses `SettingsService`.
- **Cons**: Opaque JSON value; list/filter/enable/disable queries are clumsy (string-prefix scans + JSON parsing); no column-level constraints; mixes two very different override shapes (scalar vs structured object) in one table.
- **Effort**: M.

### Approach C — Write back to YAML files at runtime
**Description**: CLI/API edit the `sources.d/*.yaml` files directly on disk.
- **Pros**: No DB, no merge layer; YAML stays the single source of truth.
- **Cons**: Breaks on read-only/ephemeral deploys (Railway containers, desktop); concurrent-write hazards; changes lost on redeploy unless committed; diverges from the established DB-override pattern the user explicitly asked to extend.
- **Effort**: M.

**Recommendation**: Approach A. It directly fulfills the request to extend the DB-override mechanism, keeps validation in one place via the existing source union, and confines runtime behavior change to a single function while remaining robust on ephemeral/read-only deploys (where Approach C fails).
