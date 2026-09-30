## ADDED Requirements

### Requirement: Substack Session Expiry Detection

The Substack adapter SHALL judge every response to a request that carried
`substack.sid` and SHALL treat as a dead session exactly these answers: HTTP 401;
HTTP 403 without a `cf-mitigated` header; a redirect whose `Location` path is
`/sign-in` or `/account/login`; and a 2xx `text/html` body from a JSON API
endpoint. Requests sent without a cookie SHALL NOT be judged. On a dead session
the adapter SHALL call `CredentialProvider.refresh()` once and retry the request
once when the refresh produced a different cookie. When the session is still
refused, the adapter SHALL record `mark_rejected("SUBSTACK_SESSION_COOKIE")` and
raise `SessionExpiredError`. A 2xx from an endpoint that requires a login SHALL
call `mark_verified("SUBSTACK_SESSION_COOKIE")`; a public endpoint SHALL NOT.

#### Scenario: Login redirect after one refresh
- **WHEN** the session probe answers 302 to `https://substack.com/sign-in` and the retry with the refreshed cookie is also redirected
- **THEN** exactly one refresh and one retry were made
- **AND** `SessionExpiredError` is raised and `metadata("SUBSTACK_SESSION_COOKIE").rejected_at` is set

#### Scenario: Refresh heals the session
- **WHEN** the probe answers 401 for the cached cookie and OpenBao holds a new cookie that Substack accepts
- **THEN** the retry succeeds, the run ingests posts, and `last_verified_at` is set

#### Scenario: Cloudflare challenge is not a session verdict
- **WHEN** a cookie-bearing request answers 403 with `cf-mitigated: challenge`
- **THEN** no refresh is attempted and no `SessionExpiredError` is raised

### Requirement: Session-Expired Runs Fail Closed

A Substack ingestion run with a configured cookie SHALL prove the session with
one authenticated request before fetching, and SHALL fetch every source before
persisting any row. When `SessionExpiredError` is raised at any point of the
fetch phase, the run SHALL persist zero rows and return `status=error`,
`items_ingested=0`, and one error with code `session_expired`. The codes
`session_expired` and `credentials_missing` SHALL be part of the closed public
ingestion diagnostic vocabulary so the durable operation result keeps them. A
run without any cookie is governed by the "Cookie-less Substack Runs Fail
Closed" requirement of change
`authenticate-substack-post-fetches-with-the-session-cookie`.

#### Scenario: Zero rows on an HTML login page
- **WHEN** the probe answers 200 `text/html` for both the cached and the refreshed cookie
- **THEN** the response has `status=error`, `items_ingested=0`, and error code `session_expired`
- **AND** no database session was opened

#### Scenario: Session dies mid-run
- **WHEN** the probe is inconclusive, the first publication's archive succeeds, and the second publication's archive redirects to `/sign-in`
- **THEN** the run persists zero rows and reports `session_expired`

### Requirement: Typed Session Failure Without Values

`SessionExpiredError` SHALL derive from a reusable `CredentialFailureError` that
carries the source key, the credential label, and the refresh command, and
converts to an `IngestionError` with its stable code. Neither the exception, its
arguments, the envelope, nor any log record SHALL contain a credential value.

#### Scenario: Error names the label and command only
- **WHEN** a Substack session is refused
- **THEN** the error message contains `substack.sid` and `aca auth session substack`
- **AND** no cookie value appears in the exception, the response JSON, or captured logs

### Requirement: Credential Rejection Metadata

`CredentialProvider.mark_rejected(name)` SHALL record, in process memory only, a
`rejected_at` bound to the current value's fingerprint, exposed through
`CredentialMetadata.rejected_at`. A rotated value SHALL NOT inherit the
rejection, `mark_verified(name)` SHALL clear it, and recording it SHALL NOT write
to OpenBao.

#### Scenario: Rotation clears a rejection
- **WHEN** a cookie is marked rejected and OpenBao is then refreshed with a new cookie
- **THEN** `metadata(...).rejected_at` is none and nothing was written to OpenBao
