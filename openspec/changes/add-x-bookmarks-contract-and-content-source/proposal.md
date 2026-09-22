# Add x_bookmarks to the workflow contract and ContentSource enum

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-x-bookmarks-contract-and-content-source`
> Effort: M
> Priority: 1

## Summary

Add XBookmarksIngestCommand to openspec/contracts/content-workflows/openapi/v1.yaml, regenerate src/contracts/workflow_models.py, add ingest.x-bookmarks and x_bookmarks to the closed literals in src/ingestion/result.py and COMMAND_MODELS, and add X_BOOKMARKS to ContentSource with an idempotent Alembic enum migration.

## Dependencies

- None

## Acceptance Outcomes

- src/contracts/workflow_models.py contains XBookmarksIngestCommand and matches a fresh regeneration from openapi/v1.yaml with no hand edits.
- alembic heads reports a single head and the migration uses ALTER TYPE contentsource ADD VALUE IF NOT EXISTS so it is idempotent.
- Contract tests accept ingest.x-bookmarks and x_bookmarks as valid literals.

## Rationale

Canonical sources are contract-first; the generated models, closed literals, and PG enum must exist before any descriptor or adapter can be registered.
