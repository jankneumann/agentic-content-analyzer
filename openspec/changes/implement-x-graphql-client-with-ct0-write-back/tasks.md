# Tasks: Implement X GraphQL client with query ID discovery and ct0 write-back

> Change ID: `implement-x-graphql-client-with-ct0-write-back`

## 1. Plan

- [x] 1.1 Read the exporter's `api.ts` (headers, features, discovery, pagination, 429, parsing)
- [x] 1.2 Trace reusable pieces: `x_web_headers`, `CredentialProvider`, `credential_failures`, `BaoSink`, `bao_secrets`
- [x] 1.3 Choose the query ID cache (`settings_overrides` via `SettingsService`; no migration)
- [x] 1.4 Move the spec delta to `x-bookmarks-ingestion`

## 2. Implement

- [x] 2.1 `XPost` / `BookmarksPage` records and `parse_tweet_result` / `parse_bookmarks_page` (note tweets, quoted post, media variants, expanded URLs)
- [x] 2.2 Query ID discovery from the runtime chunk map and `main.js`; bundle requests without the session
- [x] 2.3 `SettingsQueryIdStore`; invalidate, rediscover once and retry once on 404 or "query not found"
- [x] 2.4 `iter_pages` / `BookmarkWalk`: cursor walk, `stop_when`, page cap, page size, page delay, stop reasons
- [x] 2.5 429 handling with `x-rate-limit-reset` and a capped wait
- [x] 2.6 Dead-session predicate, one refresh and one retry, `mark_rejected` + `SessionExpiredError`; `CredentialsMissingError`; `mark_verified`
- [x] 2.7 ct0 write-back: one `BaoSink.write()` of the pair on the worker's client, `apply_local_write` with the sink's `saved_at`, local-only without OpenBao, never failing the fetch
- [x] 2.8 `bao_secrets.is_bao_configured()` / `get_authenticated_bao_client()`; `x_bookmarks_page_delay_s` setting

## 3. Test

- [x] 3.1 Discovery from the runtime chunk map (hash suffix fallback) and from `main.js`; no session sent to `abs.twimg.com`
- [x] 3.2 Cached ID reused without scraping; 404 and GraphQL "query not found" rediscover once; second stale answer raises; failed cache clear not re-read
- [x] 3.3 Two-page cursor walk; `stop_when` stops after page one; page cap; repeated cursor; caller break
- [x] 3.4 429 with reset honoured (fake clock); long reset stops with `rate_limited`; repeated 429s stop
- [x] 3.5 Rotated ct0 written once through a fake hvac adapter (merge-patch, both keys and `_SAVED_AT`), next request uses it; unchanged/deleted ct0 not written; no-OpenBao and failing-sink paths
- [x] 3.6 401 -> refresh -> still dead -> `SessionExpiredError` + both rejected; refreshed pair retried; recovery; HTML login page; login redirect on discovery; Cloudflare 403 not a verdict; network errors by type with no chained request
- [x] 3.7 Missing cookie -> `CredentialsMissingError` before any request
- [x] 3.8 Record mapping (note tweet, quoted post, legacy author shape, media, links, unescaping, tombstones)
- [x] 3.9 `SettingsQueryIdStore` against Postgres and fail-open without a database
- [x] 3.10 No sentinel cookie or bearer value in log records, stdout, or stderr (autouse check)

## 4. Validate

- [x] 4.1 `uvx ruff@0.15.15 check` / `format`, `mypy` on changed sources
- [x] 4.2 Targeted pytest and `openspec validate --strict`
