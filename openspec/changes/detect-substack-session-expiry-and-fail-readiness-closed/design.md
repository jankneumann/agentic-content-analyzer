# Design: Detect Substack session expiry and fail readiness closed

## Where the cookie actually travels

`SubstackClient.fetch_posts()` first calls `substack_api.Newsletter` /
`Post` with `auth=None`; that library uses its own `requests` session and never
sees `substack.sid`. The cookie only reaches Substack through our `httpx`
client: the two subscription endpoints and the `/api/v1/archive` fallback
(used only when the library path fails). Consequences:

1. Watching only the archive fallback would almost never notice a dead
   session. The adapter therefore proves the cookie once per run with an
   authenticated probe (`GET https://substack.com/api/v1/subscriptions`, the
   endpoint the sync already uses) before fetching.
2. Paid post bodies are fetched logged out even with a valid cookie. This is
   pre-existing and out of scope (routing the library through the
   authenticated client changes redirect and custom-domain behaviour); it is
   reported as a follow-up.

## Dead-session predicate

Only a request that carried a cookie is judged; a logged-out request is
expected to look logged out. Signals, each one a logged-in request never
produces:

| Answer | Verdict |
|---|---|
| 401 | dead |
| 403 | dead, unless `cf-mitigated` is present (Cloudflare bot challenge) |
| 3xx whose `Location` path is `/sign-in` or `/account/login` (the client never follows redirects) | dead |
| 2xx `text/html` from a JSON API endpoint | dead |
| 404, 429, 5xx, other redirects, network errors | not a session verdict; existing handling |

## Refresh once, retry once

On a dead answer the client calls `provider.refresh()` (bounded process-wide
by ri-04) and re-resolves the cookie. It retries the request once only when
the cookie changed; retrying the same refused value would be a wasted request.
Still dead (or unchanged) raises `SessionExpiredError` and records
`mark_rejected()`. An explicit `session_cookie` override is never refreshed
and never recorded on the provider, because it did not come from it.

`mark_verified()` is called only for a 2xx from an endpoint that requires a
login (probe, subscriptions). The archive is public, so its 200 proves nothing.

## Failing closed

`ingest_content()` already fetched every source before its persistence loop.
The fetch phase moved into `_fetch_contents()`; `SessionExpiredError` raised
anywhere in it (probe or a later archive fallback) returns
`IngestionResponse(status="error", items_ingested=0, errors=[session_expired])`
before `get_db()` is opened. The canonical workflow handler attaches that
result and marks the operation failed; the sanitizer keeps the code.

## No cookie: warn, do not fail (superseded by ri-18)

> **Superseded.** `authenticate-substack-post-fetches-with-the-session-cookie`
> (ri-18) routed the post-body fetch through the authenticated client, which
> is the condition the last paragraph below names. A Substack run without a
> cookie now fails closed with `credentials_missing` and zero rows, and the
> envelope warning is gone. See that change's design.md. The reasoning below
> is kept as the record of why ri-05 did not fail closed.

The brief asks whether cookie-less Substack ingestion is useless. From the
code: no. Because the post path never sends the cookie (above), a cookie-less
run fetches exactly the same bodies as a cookied run: full free posts from the
configured publications and whatever Substack serves logged out for paywalled
ones. Failing closed on a missing cookie would drop content that is
obtainable today without any credential. So the run keeps today's behaviour
and adds a `credentials_missing` warning to the envelope (status stays `ok`).

An expired cookie is different: it is an operator state that must be fixed,
and the acceptance outcome requires zero rows. Readiness is advisory (its only
consumer is `CapabilityService.list_configured_sources`; nothing gates runs on
it), so reporting `credentials_missing` there while a run still ingests public
posts is consistent: readiness answers "is the paid session usable?".

Revisit this once the library path is authenticated: then a cookie-less
paid-source run is mostly teasers, which also poison dedup (a later
authenticated run skips the `source_id`), and failing closed becomes right.

## Readiness through the provider

`_substack_readiness` reads `get_credential_provider().metadata()` (never
`Settings`): absent means `credentials_missing`; `rejected_at` for the current
value means `session_expired`; otherwise ready. `rejected_at` is bound to the
value's fingerprint, so patching a fresh cookie into the OpenBao cache (token
manager refresh, `refresh()`, or `apply_local_write()`) flips readiness in the
same process with no restart. Like `last_verified_at`, the rejection lives in
the memory of the process that saw it: the worker. An API process listing
configured sources does not see a worker's rejection; ri-06/ri-16 own the
durable, cross-process signal (the failed operation already carries the code).

## Code vocabulary

`credentials_missing` rather than the gmail-style `<kind>_unavailable` or the
roadmap's `x_bookmarks_credentials_missing`: readiness is already keyed by
source, so one source-agnostic word per condition lets the X source reuse it.

Closed lists checked (CLAUDE.md gotcha):

- `src/ingestion/result_sanitizer.py` `_SAFE_DIAGNOSTIC_MESSAGES`: extended.
  Without it the durable result would say `unexpected_error`.
- `openapi/v1.yaml` `BoundedDiagnostic.code` and
  `ConfiguredSource.readiness_code`: open strings, no edit.
- `IngestionError.code` / `IngestionWarning.code`: open strings.
- `src/contracts/workflow_alert_models.py` `WorkflowAlertDiagnosticCode` and
  the `codes.items.enum` of
  `openspec/changes/production-telemetry-and-out-of-band-alerting/contracts/workflow-alert-envelope.schema.json`:
  NOT extended. `_ingestion_codes()` drops unknown codes, so the failed
  operation still produces its terminal event and alert, only without
  `session_expired` in `codes`. Classifying it (severity, refresh command in
  the body, the two lists changed together, proven with the real emitter) is
  ri-16's stated scope; widening one list here without the other would be the
  half-widening the gotcha warns about.

## Non-goals

- Authenticating the substack-api library path (done in ri-18, which replaced it).
- Removing the pre-existing `session_cookie` override (reported separately).
- Hoverfly simulations: tests use `httpx.MockTransport`, which exercises the
  same client code network-free.
