# Tasks: Authenticate Substack post fetches with the session cookie

> Change ID: `authenticate-substack-post-fetches-with-the-session-cookie`

## 1. Planning

- [x] 1.1 Inspect `substack_api` 1.3.1: auth is cookies-file only; list the JSON endpoints it calls
- [x] 1.2 Confirm the `substack` source type is paid-only (`substack-sync` routing, SETUP docs)
- [x] 1.3 Write proposal, design, and the `browser-session-credentials` spec delta

## 2. Authenticated post fetch

- [x] 2.1 Replace `_fetch_posts_from_api`/`_fetch_posts_from_http` with `_fetch_archive` + `_fetch_post_detail` through `_get_with_session`
- [x] 2.2 Build post URLs from the configured publication and a validated slug
- [x] 2.3 Follow one same-path host-move redirect; no other redirects
- [x] 2.4 Remove the `substack_api` import and `_get_auth()`; browser-like default headers

## 3. Paid teaser detection

- [x] 3.1 `is_paid_post()` / `is_teaser_body()` from `audience`, body presence, `wordcount`
- [x] 3.2 Record `substack_body` and `audience` in `metadata_json`; log a teaser count

## 4. Fail closed without a cookie

- [x] 4.1 `CredentialsMissingError` in `src/ingestion/credential_failures.py`
- [x] 4.2 `SubstackClient.require_session_cookie()` with one bounded refresh
- [x] 4.3 `ingest_content()` returns zero rows with `credentials_missing`; remove the ri-05 warning
- [x] 4.4 `real_ingest_policy`: `substack` credentialed on `SUBSTACK_SESSION_COOKIE`
- [x] 4.5 Mark ri-05 design/spec/proposal superseded; replace its cookie-less test

## 5. Teaser upgrade

- [x] 5.1 `is_teaser_upgrade()` (marked teaser, or legacy row under 80% of the full body's words)
- [x] 5.2 `_upgrade_teaser()`: overwrite, delete summaries, status `parsed` (keep `filtered_out`, skip `processing`)

## 6. Host review

- [x] 6.1 Publication 403 is ambiguous: re-probe once per run; probe ok -> `substack.post_access_denied`, teaser kept, no `mark_rejected`; probe dead -> `session_expired`
- [x] 6.2 `substack_request_delay_s` (default 1.0) paces post-detail requests; `request_delay_s`/`sleep` seam
- [x] 6.3 Tests for both 403 branches, archive 403, Cloudflare 403, pacing, and the setting default

## 7. Tests and docs

- [x] 7.1 `tests/ingestion/test_substack_paid_posts.py`: four acceptance outcomes (MockTransport, real DB for the upgrade)
- [x] 7.2 Existing substack suites pass
- [x] 7.3 `docs/SETUP.md` Substack section and `docs/TESTING.md` live policy
- [x] 7.4 ruff 0.15.15, mypy, `openspec validate --strict`
