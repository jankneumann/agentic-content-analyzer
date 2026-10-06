# Authenticate Substack post fetches with the session cookie

> Parent roadmap: `x-bookmarks-session-capture` · item `ri-18` · effort M · depends on `ri-05`

## Why

`SubstackClient.fetch_posts()` fetched post lists and bodies through the
`substack_api` library with `auth=None`. That library only authenticates from a
cookies *file* (`SubstackAuth(cookies_path)`) and uses its own `requests`
session, so paid posts were fetched logged out even with a valid `substack.sid`.
Capturing (ri-08) and rotating (ri-04, ri-05) the cookie therefore changed
nothing about the content. Because the body was a teaser either way, ri-05 kept
cookie-less runs "succeeding" with a warning, and dedup kept those teaser rows
forever.

## What Changes

- **httpx replaces the library on the post path.** `fetch_posts()` lists
  `<publication>/api/v1/archive` and fetches each `<publication>/api/v1/posts/<slug>`
  (the endpoints the library used) through `_get_with_session()`, so every
  request carries the live cookie and gets the ri-05 dead-session policy
  (refresh once, retry once, `session_expired`). One same-path host-move
  redirect is followed; unsafe slugs are never requested. The
  `substack_api` import and the dead `_get_auth()` are removed.
- **Ambiguous 403 and pacing.** A 403 from an archive or post request is
  settled by one re-probe per run: a live session means per-post access
  denied (teaser kept, `substack.post_access_denied`), a dead one means
  `session_expired`. Post requests are paced by the new
  `substack_request_delay_s` setting (default 1.0 s).
- **Paid teaser detection.** `is_teaser_body()` flags an `only_paid`/`founding`
  post with no body or with under 80% of its `wordcount`. Rows record
  `metadata_json.substack_body` (`full`/`teaser`) and `audience`.
- **Cookie-less runs fail closed.** A run with enabled sources and no cookie
  (after one bounded provider refresh) sends nothing and returns zero rows with
  `credentials_missing` via a new `CredentialsMissingError`. The ri-05 envelope
  warning is removed; ri-05's design/spec/tests are marked superseded.
  `real_ingest_policy` now treats `substack` as credentialed on
  `SUBSTACK_SESSION_COOKIE` (matching `openspec/specs/real-ingestion-ci`).
- **Teaser upgrade.** An existing row (same `source_id`) that is a teaser is
  overwritten by a fresh full paid body, its summaries deleted, and its status
  reset to `parsed`; everything else is still skipped by dedup.

## Impact

- Code: `src/ingestion/substack.py`, `src/ingestion/credential_failures.py`,
  `src/ingestion/real_ingest_policy.py`, `src/config/settings.py`
  (`substack_request_delay_s`).
- Tests: `tests/ingestion/test_substack_paid_posts.py` (new);
  `test_substack_session_expiry.py` and `test_substack_live_credentials.py`
  adjusted to the removed library path and the fail-closed behaviour.
- Docs: `docs/SETUP.md` (Substack section), `docs/TESTING.md` (live policy).
- Specs: `browser-session-credentials` (ADDED).
- Operators: a Substack run with no cookie is now a failed operation with
  `credentials_missing`. Free publications belong in `rss.yaml` (where
  `aca ingest substack-sync` already puts them).
- No contract, migration, CLI, or API change; one new setting. `substack-api` stays in
  `pyproject.toml` (now unused by the adapter; removing it is a follow-up).
