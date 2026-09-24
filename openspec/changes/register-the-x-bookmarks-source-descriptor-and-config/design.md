# Design: Register the x_bookmarks source descriptor and config

## Decisions

- **Fixed locator.** One configured X session means one bookmarks source.
  `source_key()` returns `x_bookmarks:account` for every `x_bookmarks` entry,
  ignoring `name` and `url`. Readwise, the other singleton, falls back to its
  name; X does not, so renaming the entry keeps its DB override and opaque
  public key. Two entries collapse to one identity; the planner uses the first.
- **Readiness needs the pair.** `auth_token` without `ct0` (or the reverse)
  cannot authenticate, so readiness is `credentials_missing` unless both are
  present, and `session_expired` if either current value is marked rejected.
  It reads only through `get_credential_provider()`, so a pair patched into
  OpenBao flips readiness without a restart. Shared codes come from
  `src/ingestion/credential_failures.py` (ri-05 replaced the per-source
  `x_bookmarks_credentials_missing` with the shared `credentials_missing`).
- **Planner ignores the period.** X does not expose when a post was
  bookmarked; the adapter stops at the first fully known page and `--full`
  overrides that. `max_entries` becomes `max_items`, and `expand_links` is
  planned explicitly from config so the queued command is self-describing.
- **Fail closed before the adapter exists.** `ingest_x_bookmarks` returns an
  `IngestionResponse` with `status=error` and code `source_unavailable`, which
  the closed diagnostic vocabulary admits. It never raises, never calls the
  network, and never persists, so an enabled source yields a clean failed
  operation rather than a traceback or a partial run.
- **Disabled by default, no schedule of its own.** `sources.d` has no
  per-source schedule; scheduling follows the pipeline. Shipping the entry
  disabled keeps a fresh install's scheduled pipeline green. The quiet-hour
  schedule from the roadmap belongs with the adapter (ri-12), once a run does
  real work.
- **Live policy: all-of credentials.** `LiveAdapterPolicy` gains
  `requires_all_credentials`; only `x_bookmarks` sets it.

## Non-goals

The HTTP client, GraphQL query-ID discovery, `ct0` write-back (ri-11), the
adapter and persistence (ri-12), link expansion, and documentation (ri-17).
