# Register the x_bookmarks source descriptor and config

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-10`)
> Change ID: `register-the-x-bookmarks-source-descriptor-and-config`
> Effort: M · Priority: 2 · Depends on: `ri-09`, `ri-04`

## Why

ri-09 added `XBookmarksIngestCommand` to the canonical contract, but the
executable `SOURCE_REGISTRY` has no `x_bookmarks` descriptor. The capability
document therefore disagrees with the OpenAPI discriminator
(`test_capabilities_match_openapi_discriminator_and_fields` is red), and a
submitted `x_bookmarks` command cannot be dispatched. Registering through
`src/ingestion/registry.py` is the only way the CLI, HTTP, MCP, and frontend
transports all learn the source, and the fixture-registry completeness check
requires every registry source to have a network-free fixture.

This item delivers the registry and configuration layer only. The HTTP client
(ri-11) and the adapter with persistence (ri-12) come later, so the
orchestrator entry must fail closed until they land.

## What Changes

- `src/config/sources.py`: `XBookmarksSource` (`type: x_bookmarks`,
  `expand_links: bool = False`, `max_entries` bounded 1..10000 like the
  command's `max_items`) joins the `Source` union, with
  `SourcesConfig.get_x_bookmarks_sources()`. It is a single-account source:
  `source_key()` always returns `x_bookmarks:account`
  (`X_BOOKMARKS_LOCATOR`), whatever the entry is named, so a DB override lines
  up with the YAML entry and renaming does not change identity.
- `sources.d/x_bookmarks.yaml`: one entry, `enabled: false`, `max_entries: 100`,
  `expand_links: false`, with a comment naming `aca auth session x`, the two
  credentials, and how to enable it. A fresh install does not plan it.
- `src/ingestion/registry.py`: `SourceDescriptor("x_bookmarks", "X Bookmarks",
  XBookmarksIngestCommand, ...)`, scheduled, with a bulk planner that maps the
  first configured source's `max_entries` to `max_items` and `expand_links`
  from config and ignores the period (X does not expose bookmark time).
  `_x_bookmarks_readiness` reads `X_AUTH_TOKEN` and `X_CT0` through
  `get_credential_provider()`: `credentials_missing` unless both are present,
  `session_expired` while either current value is marked rejected,
  `source_unavailable` if the provider itself fails, ready otherwise.
- `src/ingestion/orchestrator.py`: `ingest_x_bookmarks(max_items, full,
  expand_links, force_reprocess)` fails closed: no network call, zero rows,
  `status=error` with one `source_unavailable` error. The durable operation
  records it as a failed ingestion with the sanitized code. ri-12 replaces the
  body.
- `src/ingestion/real_ingest_policy.py`: `x_bookmarks` is credentialed on
  `X_AUTH_TOKEN` and `X_CT0` together, through a new
  `requires_all_credentials` flag (other sources keep any-of semantics).
- `src/services/capability_service.py`: `expand_links` joins the public
  configuration allowlist (a boolean).
- `tests/fixtures/sources/library.py`: a network-free `x_bookmarks` fixture
  with an explicit configured-source snapshot.

## Impact

- Affected specs: `source-configuration`, `source-capability-registry`,
  `real-ingestion-ci`.
- Affected code: the files above, plus `tests/ingestion/test_source_registry.py`
  and the new `tests/ingestion/test_x_bookmarks_registry.py`.
- No contract, migration, or web change: ri-09 already shipped the contract,
  enum, MCP tool, and frontend display. The web settings "add source" form's
  `SourceType` list is curated (Readwise and Obsidian are absent too), and the
  sources list and ingest surfaces are capability-driven.
- The legacy `ingest_content` worker map in `src/queue/worker.py` is not
  touched: its only producer (`POST /api/v1/contents/ingest`) is retired, and
  the canonical path dispatches through `IngestionService` and the registry.
