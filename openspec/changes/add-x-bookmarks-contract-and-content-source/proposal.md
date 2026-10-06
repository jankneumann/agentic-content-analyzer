# Add x_bookmarks to the workflow contract and ContentSource enum

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-09`)

## Why

Canonical sources are contract first. Before a `SourceDescriptor`, source config,
or adapter for X bookmarks can be registered (ri-10, ri-11), the typed command,
the closed response literals, and the persisted `contentsource` enum value must
exist, and every surface that enumerates contract commands or content sources
must agree on them.

## What Changes

- `openspec/contracts/content-workflows/openapi/v1.yaml`: add a strict
  `XBookmarksIngestCommand` (`kind: x_bookmarks`; `max_items` 1 to 10000, `full`,
  `expand_links`, `force_reprocess`, internal `configured_sources`), register it
  in the `IngestCommand` oneOf and discriminator, and add `x_bookmarks` to
  `ContentQuery.source_types`.
- Regenerate `src/contracts/workflow_models.py`, `generated/models.py`,
  `generated/types.ts`, and `web/src/generated/workflow-contracts.ts` with
  `scripts/generate_workflow_contracts.py`.
- `src/ingestion/result.py`: add `ingest.x-bookmarks` and `x_bookmarks` to the
  closed literals. `src/ingestion/commands.py`: export the model in `COMMAND_MODELS`.
- `src/models/content.py`: add `ContentSource.X_BOOKMARKS`; the Alembic migration
  `d8e2a4c6f1b3` adds the value with `ADD VALUE IF NOT EXISTS` (no-op downgrade),
  and the contract DDL `db/schema.sql` records the same statement.
- Transport lists the contract tests enforce: the MCP `ingest_x_bookmarks` tool
  and its canonical manifest entry, plus the frontend source display map (required
  by `Record<ContentSource, …>`), source filter, and contents filter.
- Tests: contract, response literal, migration, and MCP coverage for the new
  command, plus a frontend badge test.

## Impact

- Affected specs: new capability `x-bookmarks-ingestion`.
- The CLI subcommand `aca ingest x-bookmarks` appears automatically because the
  CLI is generated from `COMMAND_FIELD_SCHEMAS`.
- Out of scope (ri-10): `XBookmarksSource`, `sources.d/x_bookmarks.yaml`, the
  `SourceDescriptor`, the readiness resolver, the real-ingest policy entry, the
  worker dispatch, and the network-free fixture. Until ri-10 lands, the contract
  lists a command that the registry cannot yet dispatch, so
  `tests/services/test_capability_service.py::test_capabilities_match_openapi_discriminator_and_fields`
  fails, and a submission of `kind: x_bookmarks` raises from `SOURCE_REGISTRY.get`.
  Land ri-10 before this reaches a deployed environment.
