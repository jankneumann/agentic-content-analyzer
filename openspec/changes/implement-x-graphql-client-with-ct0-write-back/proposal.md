# Implement X GraphQL client with query ID discovery and ct0 write-back

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-11`)
> Change ID: `implement-x-graphql-client-with-ct0-write-back`
> Effort: M · Priority: 1 · Depends on: `ri-02`, `ri-04`, `ri-05`

## Why

The `x_bookmarks` source is registered (ri-10) but its orchestrator fails
closed because nothing can read X bookmarks from Python. The only working
reader is the MIT-licensed x-bookmarks-exporter, a Node CLI; the worker image
is python:3.12-slim and must not grow a Node runtime or shell out. X's web app
also rotates the `ct0` cookie routinely: unless the worker writes the new
value back, the stored session goes stale and a human has to re-capture it
long before the yearly `auth_token` expiry.

This item ports the exporter's fetch layer to httpx and delivers the HTTP
client only. Persistence and the orchestrator body are ri-12; link expansion
is ri-13.

## What Changes

- New `src/ingestion/x_bookmarks_client.py`:
  - `XBookmarksClient.iter_pages(stop_when=, max_pages=)` returns a
    `BookmarkWalk` that yields `BookmarksPage`s newest-first by the
    `cursor-bottom` entries, with a hard page cap (default 50, at most 500),
    a conservative page size (default 20, at most 100), a pause between pages
    (`x_bookmarks_page_delay_s`, default 1 s), and a `stop_when(page_ids)`
    hook evaluated after each page. `stop_reason` reports `exhausted`,
    `stop_when`, `page_cap`, `rate_limited`, or `caller_stopped`.
  - Requests use `x_web_headers()` (public web-app bearer, `auth_token`/`ct0`
    cookie, `x-csrf-token`), the exporter's `features`/`fieldToggles`, and
    credentials read per request from `get_credential_provider()`.
  - Query ID discovery from the authenticated `/i/bookmarks` page: the
    inlined webpack runtime's chunk map to the `bundle.Bookmarks` chunk
    (with the exporter's 7/8-character hash fallback), then `main.<hash>.js`.
    Bundle requests to `abs.twimg.com` never carry the session. The last good
    ID is cached in `settings_overrides` under
    `x_bookmarks.graphql_query_id` (`SettingsQueryIdStore`, fail-open). A 404
    or a GraphQL "query not found" error invalidates it, rediscovers once and
    retries once; a second stale answer raises `QueryIdDiscoveryError`.
  - 429 waits until `x-rate-limit-reset` (at least 5 s, 60 s without the
    header) when that is at most 15 minutes away and at most twice per page;
    otherwise the walk stops with `rate_limited` and `rate_limit_reset_at`,
    keeping the pages already yielded.
  - Dead session (401, non-Cloudflare 403, redirect into the login flow, HTML
    in place of JSON, JSON session error codes; for the discovery page a
    login page): `provider.refresh()` once, one retry if the pair changed,
    then `mark_rejected` on both credentials and `SessionExpiredError`
    (`aca auth session x`). A missing cookie after one refresh raises
    `CredentialsMissingError` before any request. A GraphQL success calls
    `mark_verified` on both.
  - `Set-Cookie: ct0=<new>` on any non-dead response is written back before
    the response is parsed: `X_AUTH_TOKEN` and `X_CT0` in ONE `BaoSink.write()`
    on the worker's authenticated hvac client, then
    `provider.apply_local_write(..., saved_at=<the sink's saved_at>)`.
    Without OpenBao only the local cache is updated and a value-free warning
    is logged. The next request uses the new `ct0`. A write-back failure is
    logged by type and never fails the fetch.
  - Value-free records: `XPost` (id, canonical URL, note-tweet full text with
    `t.co` links expanded, author id/handle/name, UTC `created_at`,
    conversation and reply ids, outbound URLs without X self links, media
    URLs with the best mp4 variant, hashtags, mentions, counts, one level of
    quoted post) and `BookmarksPage`.
- `src/config/bao_secrets.py`: public `is_bao_configured()` and
  `get_authenticated_bao_client()` so the write-back reuses the worker's
  AppRole login.
- `src/config/settings.py`: `x_bookmarks_page_delay_s` (default 1.0).
- `tests/fixtures/x_bookmarks_graphql.py`: builders shaped like real Bookmarks
  GraphQL responses, the `/i/bookmarks` HTML shell, and the bundles, for this
  item and ri-12.

## Impact

- Affected spec: `x-bookmarks-ingestion` (ADDED requirements).
- No migration: the query ID reuses `settings_overrides`; `alembic heads`
  stays at the single existing head.
- No contract, API, CLI, or worker-dispatch change; nothing calls the client
  until ri-12.
- The worker AppRole already holds `patch` on the secret path (ri-03).
