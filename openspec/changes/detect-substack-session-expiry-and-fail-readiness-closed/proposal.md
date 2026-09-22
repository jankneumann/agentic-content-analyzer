# Detect Substack session expiry and fail readiness closed

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-05`)
> Change ID: `detect-substack-session-expiry-and-fail-readiness-closed`
> Effort: M · Priority: 2 · Depends on: `ri-04`

## Why

`SubstackClient` sends `substack.sid` (resolved live through ri-04's
`CredentialProvider`) but never looks at how Substack answers it. An expired
cookie produces a sign-in redirect, an HTML login page, or a 401, which the
HTTP fallbacks swallow as a generic warning. The run then "succeeds" on the
public posts, the operator never learns the session is dead, and
`fetch_subscriptions()` even returns `[]`, which would make
`sync_substack_sources()` rewrite `substack.yaml` with no sources. The
effort requires credential-gated sources to report a stable code and fail
closed rather than run partially.

## What Changes

- New `src/ingestion/credential_failures.py`: `CREDENTIALS_MISSING` /
  `SESSION_EXPIRED` codes and a reusable `CredentialFailureError` base with
  `SessionExpiredError`. Each carries the source, the credential LABEL
  (`substack.sid`) and the refresh command, never the value, and converts to
  an `IngestionError`. The X adapter (ri-11/ri-12) reuses it.
- `src/ingestion/substack.py`:
  - `is_dead_session_response()`: 401; 403 unless a Cloudflare challenge
    (`cf-mitigated`); a redirect to `/sign-in` or `/account/login`; a 2xx
    `text/html` body on a JSON endpoint. Only requests that carried a cookie
    are judged.
  - Every cookie-bearing request (subscription endpoints, archive fallback,
    new probe) goes through `_get_with_session()`: on a dead answer it calls
    `provider.refresh()` once, retries once if that produced a different
    cookie, and otherwise raises `SessionExpiredError` after
    `provider.mark_rejected()`. A 2xx from a login-only endpoint calls
    `provider.mark_verified()`; the public archive never does.
  - `SubstackClient.verify_session()`: one authenticated probe
    (`https://substack.com/api/v1/subscriptions`), reusable by ri-08.
  - `SubstackContentIngestionService.ingest_content()` probes the session
    before fetching and fetches every source before persisting anything, so a
    `SessionExpiredError` anywhere returns `status=error`, `items_ingested=0`,
    and one `session_expired` error: zero rows, never a partial run.
  - A cookie-less run keeps today's behaviour (public posts) and adds a
    `credentials_missing` warning to the envelope (see design.md).
  - `fetch_subscriptions()` raises instead of returning `[]` on a dead
    session.
- `src/config/credentials.py`: `CredentialProvider.mark_rejected(name)` and
  `CredentialMetadata.rejected_at`, in-process and bound to the value's
  fingerprint like `last_verified_at`; `mark_verified` clears a rejection.
- `src/ingestion/registry.py`: the `substack` descriptor gets
  `_substack_readiness`, read live through the provider: `credentials_missing`
  without a cookie, `session_expired` while the current cookie is rejected,
  ready otherwise. A freshly patched cookie flips it back without a restart.
- `src/ingestion/result_sanitizer.py`: `credentials_missing` and
  `session_expired` join the closed public diagnostic vocabulary, so the
  durable operation result keeps the code instead of `unexpected_error`.

## Impact

- Affected specs: `browser-session-credentials` (added by ri-04),
  `source-capability-registry`.
- Affected code: `src/ingestion/credential_failures.py` (new),
  `src/ingestion/substack.py`, `src/ingestion/registry.py`,
  `src/ingestion/result_sanitizer.py`, `src/config/credentials.py`.
- No contract change: `IngestionResultV2` diagnostics and
  `ConfiguredSource.readiness_code` are open strings in
  `openapi/v1.yaml`. The alert vocabulary (`WorkflowAlertDiagnosticCode` and
  its JSON schema) is deliberately left to ri-16.
- One extra authenticated GET per Substack run when a cookie is configured.
