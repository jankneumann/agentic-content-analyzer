# Tasks: Add x_bookmarks to the workflow contract and ContentSource enum

> Change ID: `add-x-bookmarks-contract-and-content-source`

## 1. Contract

- [x] 1.1 Add contract tests for `XBookmarksIngestCommand` (strict fields, bounds, no credential fields, Python/TypeScript/runtime parity) and extend `SOURCE_KEYS` and the scheduled-snapshot list
- [x] 1.2 Add `XBookmarksIngestCommand` to `openapi/v1.yaml`, the `IngestCommand` oneOf and discriminator, and `x_bookmarks` to `ContentQuery.source_types`
- [x] 1.3 Regenerate with `python scripts/generate_workflow_contracts.py` and confirm `--check` reports no drift

## 2. Literals and enum

- [x] 2.1 Add `ingest.x-bookmarks` and `x_bookmarks` to the closed literals in `src/ingestion/result.py`, with a response-literal test
- [x] 2.2 Export `XBookmarksIngestCommand` in `COMMAND_MODELS` (`src/ingestion/commands.py`)
- [x] 2.3 Add `ContentSource.X_BOOKMARKS` and the Alembic migration `d8e2a4c6f1b3` (`ADD VALUE IF NOT EXISTS`, no-op downgrade); record the statement in `db/schema.sql`
- [x] 2.4 Add a migration test; verify `alembic heads` is single and `alembic upgrade head` is idempotent (twice, and downgrade then upgrade)

## 3. Transport lists

- [x] 3.1 Add the MCP `ingest_x_bookmarks` tool, its `INGESTION_TOOL_BY_SOURCE` entry, and the `CANONICAL_TOOL_NAMES` entry, with HTTP-mode and bound tests
- [x] 3.2 Add `x_bookmarks` to the frontend source display map, source filter, and contents filter, with a badge test; `pnpm typecheck` passes
- [ ] 3.3 (ri-10) Register the `SourceDescriptor`, `XBookmarksSource`, `sources.d/x_bookmarks.yaml`, the real-ingest policy, the worker dispatch, the settings-page source type, and the network-free fixture; this makes `test_capabilities_match_openapi_discriminator_and_fields` pass again

## 4. Validation

- [x] 4.1 `ruff check` and `ruff format --check` (ruff 0.15.15), `mypy` on the changed source files
- [x] 4.2 Contract, MCP, migration, registry, CLI, and API suites
- [x] 4.3 `openspec validate add-x-bookmarks-contract-and-content-source --type change --strict`
