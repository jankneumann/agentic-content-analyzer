# Tasks: Sync Substack subscriptions into database source overrides

> Change ID: `sync-substack-subscriptions-into-database-source-overrides`

## 1. Storage

- [x] 1.1 Migration: `source_overrides.managed_by VARCHAR(64) NULL`; model column; `SourceOverrideService.upsert(..., managed_by=, commit=)` and `list_overrides` expose it.

## 2. Listing

- [x] 2.1 Strict subscription listing on `SubstackClient` that raises on transport failure and re-raises `SessionExpiredError`.

## 3. Sync service

- [x] 3.1 `SubstackSubscriptionSync` planner: normalized locator index over merged YAML + DB substack/rss sources; add / existing / kept_disabled / switch / conflict / prune.
- [x] 3.2 Apply in one transaction; `--prune` disables managed rows only; refuse prune on zero subscriptions.

## 4. Surfaces

- [x] 4.1 `POST /api/v1/sources/sync/substack` (admin key; 412 with code + refresh command on credential failure); fuzz exclusion.
- [x] 4.2 `aca sources sync substack [--apply] [--prune]` with API client method and direct fallback; human and `--json` output.
- [x] 4.3 CLI descriptor lists `sources sync`.

## 5. Cleanup and docs

- [x] 5.1 Remove `sync_substack_sources()`, `_sync_paid_to_substack`, `_sync_free_to_rss`, `SyncResult`, and stale `substack-sync` docstrings.
- [x] 5.2 Update CLAUDE.md, docs/SETUP.md, docs/USER_GUIDE.md, docs/DEPLOY_SECRETS.md.

## 6. Tests

- [x] 6.1 Planner unit tests for every row of the D1 table, prune, and idempotent second apply.
- [x] 6.2 Credential failure and empty-listing prune refusal.
- [x] 6.3 API route and CLI (HTTP and direct) tests; migration test.
