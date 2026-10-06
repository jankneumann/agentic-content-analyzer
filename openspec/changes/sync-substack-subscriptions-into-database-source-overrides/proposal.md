# Sync Substack subscriptions into database source overrides

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `sync-substack-subscriptions-into-database-source-overrides`
> Effort: M
> Priority: 9

## Why

Substack subscriptions change, and following them today means hand-editing
`sources.d/substack.yaml` and `sources.d/rss.yaml`. The only code that ever
automated this, `sync_substack_sources()`, rewrites those YAML files, takes the
cookie as an argument, and has no caller since `aca ingest substack-sync` was
removed. On gx-10 the runtime home for source changes is the `source_overrides`
table (merged over YAML by `load_sources_config()`), and the session cookie is
already live through the credential provider (ri-04, ri-18).

## What Changes

- `aca sources sync substack` (dry run by default; `--apply` writes; `--prune`
  disables sync-managed rows for publications no longer subscribed) and
  `POST /api/v1/sources/sync/substack` (admin key) with the same semantics. The
  CLI uses the API by default and falls back to the database in direct mode,
  like the other `aca sources` commands.
- A new `SubstackSubscriptionSync` service lists subscriptions through the live
  session, plans against the merged YAML + database configuration, and writes
  paid publications as `substack` overrides and free ones as `rss` `/feed`
  overrides.
- `source_overrides.managed_by` (nullable) marks rows the sync created
  (`substack-sync`). Only marked rows are ever pruned, and pruning disables,
  never deletes.
- Fails closed: no or expired session gives `credentials_missing` or
  `session_expired` with `aca auth session substack`; a failed or empty listing
  never prunes.
- Removes `sync_substack_sources()`, its YAML writers and `SyncResult`, and the
  docs that describe the YAML sync.

## Non-goals

- Modifying or re-enabling any source the operator configured by hand, in YAML
  or the database, including resolving a paid/free type mismatch.
- Scheduling the sync; it runs on demand.
- Deleting override rows.

## Acceptance Outcomes

- A dry run lists the publications it would add as substack (paid) or rss (free) overrides and writes nothing.
- With --apply, each missing publication becomes one override marked managed_by=substack-sync, and a second apply with the same subscriptions writes nothing.
- A publication already configured in YAML or the database under either type, enabled or disabled, is never modified; a type mismatch is reported as a conflict.
- With --prune, sync-managed overrides for publications no longer subscribed are disabled, never deleted, and rows without the marker are never pruned.
- A missing or expired session fails closed with credentials_missing or session_expired and the refresh command, and an empty or failed subscription listing never prunes.
- sync_substack_sources() and its YAML writers are removed and no docs describe the YAML sync.
