# Register the x_bookmarks source descriptor and config

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `register-the-x-bookmarks-source-descriptor-and-config`
> Effort: M
> Priority: 2

## Summary

Add XBookmarksSource with expand_links and max_entries to the Source union, ship sources.d/x_bookmarks.yaml with a quiet-hour schedule, register a SourceDescriptor modelled on Readwise with scheduled=True, a bulk planner, and a fail-closed readiness resolver, and add a network-free fixture to tests/fixtures/sources/library.py.

## Dependencies

- `ri-09`
- `ri-04`

## Acceptance Outcomes

- aca ingest x-bookmarks submits an operation through OperationService and the CLI, HTTP, MCP, and frontend transports all list the source.
- The descriptor reports ready=false with code x_bookmarks_credentials_missing when auth_token or ct0 is unset.
- The source fixture registry test passes with x_bookmarks covered by a network-free fixture.
- sources.d/x_bookmarks.yaml schedules the source at a quiet hour with a conservative max_entries default.

## Rationale

Registering through src/ingestion/registry.py is the only way the CLI, HTTP, MCP, and frontend transports all learn the source; the fixture registry completeness check enforces it.
