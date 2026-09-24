## ADDED Requirements

### Requirement: Authenticated Substack Post Fetches

The Substack adapter SHALL fetch every post list and post body through
`SubstackClient` with `httpx`: the archive listing
(`<publication>/api/v1/archive`) and each post
(`<publication>/api/v1/posts/<slug>`, built from the configured publication URL
and a slug matching `[A-Za-z0-9][A-Za-z0-9._~-]*`). When a `substack.sid` is
configured, every such request SHALL carry the value the `CredentialProvider`
returns at the time of the request, and SHALL go through the same dead-session
policy as the session probe (refresh once, retry once, `SessionExpiredError`).
The adapter SHALL NOT use the `substack_api` library, write the cookie to disk,
or place it in argv, a log record, an exception, or the response envelope. A
redirect SHALL be followed only when it names the same API path on another
https host, and only once.

#### Scenario: Paid post ingested in full with the cookie
- **WHEN** a mocked publication serves a paid post's truncated body to a request without the paying `substack.sid` and the full body to a request with it, and that cookie is configured
- **THEN** the stored row holds the full body and `metadata_json.substack_body` is `full`

#### Scenario: Every post-fetch request carries the live cookie
- **WHEN** a run lists the archive and fetches three post bodies with a configured cookie
- **THEN** all four requests carry that `substack.sid`
- **AND** no captured log record, exception, or response JSON contains the cookie value

#### Scenario: Cookie rotated mid-run
- **WHEN** the provider's cookie changes after the first post body was fetched
- **THEN** the next post request carries the new cookie

#### Scenario: Dead session on a post body
- **WHEN** a post-body request with the cookie answers 401 before and after one refresh
- **THEN** the run persists zero rows and reports `session_expired`

### Requirement: Ambiguous Publication 403 Settled By The Probe

A non-Cloudflare 403 from an archive or post request SHALL NOT by itself be a
dead-session verdict: it SHALL NOT trigger a refresh or `mark_rejected`. The
adapter SHALL instead run the session probe once per run. When the probe finds
the session dead, the adapter SHALL raise `SessionExpiredError` and persist zero
rows. Otherwise the refused post SHALL be treated as access denied: its archive
entry is kept (a paid post without a readable body is stored as a teaser from
`truncated_body_text`), the value-free log `substack.post_access_denied` names
the slug, and the run continues. A 401, a sign-in redirect, and HTML from a
JSON endpoint SHALL remain dead-session verdicts. Post-detail requests SHALL be
separated by `substack_request_delay_s` seconds (default 1.0).

#### Scenario: Tier cannot see the post
- **WHEN** two founding-only posts answer 403 and the re-probe accepts the session
- **THEN** the run continues, stores both as teasers, probes only once more, and records no rejection

#### Scenario: Session dead behind the 403
- **WHEN** a post answers 403 and the re-probe answers 401 before and after one refresh
- **THEN** the run persists zero rows and reports `session_expired`

#### Scenario: Paced post requests
- **WHEN** a run fetches three post bodies with a 1.5 s delay configured
- **THEN** it waits 1.5 s twice, never before the first post request

### Requirement: Paid Teaser Detection

The adapter SHALL classify each post whose `audience` is `only_paid` or
`founding` as a teaser when its payload has no body, or when the body holds
fewer than 80% of the payload's integer `wordcount` words, and as full
otherwise. It SHALL record the result as `metadata_json.substack_body`
(`full` or `teaser`) together with `metadata_json.audience`. Posts with any
other `audience` SHALL NOT be classified.

#### Scenario: Teaser from a session that does not unlock the tier
- **WHEN** the configured cookie is valid but the post endpoint returns the paywalled body
- **THEN** the row is stored with `substack_body = teaser` and the run logs `substack.paid_teasers` with a count

### Requirement: Cookie-less Substack Runs Fail Closed

The `substack` source type SHALL hold paid subscriptions (`substack-sync`
routes free subscriptions to `sources.d/rss.yaml`). A Substack ingestion run with
at least one enabled source and no configured `SUBSTACK_SESSION_COOKIE` (after
one bounded `CredentialProvider.refresh()`) SHALL send no request, persist zero
rows, and return `status=error`, `items_ingested=0`, and one error with code
`credentials_missing` raised as `CredentialsMissingError` whose message names
`substack.sid` and `aca auth session substack`. The scheduled real-ingestion
tier SHALL treat `substack` as credentialed on `SUBSTACK_SESSION_COOKIE`.

#### Scenario: No cookie anywhere
- **WHEN** neither OpenBao nor `Settings` holds `SUBSTACK_SESSION_COOKIE` and a run starts with one enabled source
- **THEN** no HTTP request is sent, no database session is opened, the envelope carries error code `credentials_missing`, and the `substack` descriptor's readiness code is `credentials_missing`

#### Scenario: Cookie written to OpenBao but not yet cached
- **WHEN** the worker's OpenBao cache has no cookie but the KV path does
- **THEN** the one refresh finds it and the run proceeds authenticated

#### Scenario: Live tier without the secret
- **WHEN** the scheduled tier evaluates `substack` with `SUBSTACK_SESSION_COOKIE` unset
- **THEN** it skips the source with a reason naming `SUBSTACK_SESSION_COOKIE`

### Requirement: Substack Teaser Upgrade

When dedup finds an existing Substack row with the same `source_id`, the adapter
SHALL replace its stored body only when the fresh fetch is a paid post with
`substack_body = full` and a different content hash, and the stored row is a
teaser: recorded as `substack_body = teaser`, or, with no recorded body state,
holding fewer than 80% of the fresh body's words. The upgrade SHALL delete the
row's summaries and set its status to `parsed` so it is summarized again, except
that a `filtered_out` row keeps its status and a `processing` row is left for a
later run. Every other existing row SHALL still be skipped.

#### Scenario: Stored teaser upgraded on the next authenticated run
- **WHEN** a paid post is stored as a teaser with a summary, and an authenticated run fetches its full body
- **THEN** the same row holds the full body, `substack_body = full`, status `parsed`, and no summary

#### Scenario: Upgrade stays narrow
- **WHEN** the stored row is already full, is a free post, or is being summarized
- **THEN** the run leaves it unchanged
