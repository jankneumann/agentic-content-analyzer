## ADDED Requirements

### Requirement: Browser Session Sync Endpoint

The API SHALL expose `PUT /api/v1/browser-sessions/substack` accepting exactly
`{"substack_sid": <string>}` and `PUT /api/v1/browser-sessions/x` accepting exactly
`{"auth_token": <string>, "ct0": <string>}`. Each field SHALL be a secret string of
1 to 4096 RFC 6265 cookie-octet characters, unknown fields SHALL be rejected, and a
body declared larger than 16 KiB SHALL be rejected with 413. Every error response
on these paths SHALL be `application/problem+json`, and a request-validation error
SHALL report field paths and error codes without the submitted input.

#### Scenario: Unknown field
- **WHEN** the X body carries `auth_token`, `ct0` and an extra field
- **THEN** the API answers 422 with `code: validation_error` naming the extra field
- **AND** no submitted value appears in the response, and nothing is validated or written

#### Scenario: Header-injection attempt
- **WHEN** `ct0` contains a carriage return and line feed
- **THEN** the API answers 422 and makes no outbound request

### Requirement: Browser Session Sync Requires the Admin Key Header and Is Audited

The routes SHALL require a valid `X-Admin-Key` header. A missing key SHALL yield 401
and an invalid key 403. A web-UI session cookie or the unconfigured-development
bypass SHALL NOT authorize a write and SHALL yield 401. Every request SHALL produce an
`audit_log` row whose `admin_key_fp` is computed from the raw header whenever it is
present; routed requests SHALL carry operation `browser_sessions.sync` and notes
limited to the site, the outcome and key names.

#### Scenario: Missing key
- **WHEN** a request carries no `X-Admin-Key`
- **THEN** the API answers 401 and the audit row has `admin_key_fp` NULL and `auth_failure: missing_key`

#### Scenario: Invalid key
- **WHEN** a request carries a wrong `X-Admin-Key`
- **THEN** the API answers 403 and the audit row carries that key's SHA-256 last-8 fingerprint and `auth_failure: invalid_key`

#### Scenario: Web session only
- **WHEN** a request carries a valid web-UI session cookie and no `X-Admin-Key`
- **THEN** the API answers 401 and nothing is written

### Requirement: Browser Session Sync Validates Before One OpenBao Write

Before writing, the API SHALL make exactly one authenticated request with the same
validator the capture CLI uses. A refused session (non-200 other than 429 or 5xx, a
redirect, a non-JSON page, or JSON without the expected field) SHALL yield 422 with
`code: session_invalid`; a 429 or 5xx from the site or a transport error SHALL yield
502 with `code: session_validation_unavailable`; in both cases nothing SHALL be
written. On success the API SHALL write the site's keys (`SUBSTACK_SESSION_COOKIE`,
or `X_AUTH_TOKEN` and `X_CT0`) and their `<KEY>_SAVED_AT` siblings in ONE OpenBao KV
v2 merge-PATCH on `BAO_MOUNT_PATH/BAO_SECRET_PATH`, leaving every other key at the
path unchanged, then apply the same values and `saved_at` to its in-process
credential cache, and answer 200 with `site`, `keys_written` and `saved_at` only.

#### Scenario: Valid X session
- **WHEN** an admin PUTs a valid `auth_token`/`ct0` pair and X answers the validation request with the account's `screen_name`
- **THEN** OpenBao receives exactly one PATCH with `Content-Type: application/merge-patch+json` carrying `X_AUTH_TOKEN`, `X_CT0` and both `_SAVED_AT` keys with one timestamp
- **AND** every other key at `secret/newsletter` is byte-identical afterwards
- **AND** the response lists the four key names and the `saved_at`, and no value

#### Scenario: Expired session
- **WHEN** X answers the validation request with HTTP 401
- **THEN** the API answers 422 `session_invalid` and OpenBao receives no request

### Requirement: Browser Session Sync Writes Only to OpenBao

When OpenBao is not configured for writes (no `BAO_ADDR`, no AppRole or token
credentials, or no client library), the API SHALL answer 503 with
`code: openbao_not_configured` and a `missing` list naming the unmet requirements,
before any outbound request. It SHALL NOT fall back to a secrets file, the process
environment, or Railway. An OpenBao authentication or PATCH failure SHALL yield 502
with `code: openbao_write_failed` and a value-free hint.

#### Scenario: Server without OpenBao
- **WHEN** `BAO_ADDR` is unset and an admin PUTs a Substack session
- **THEN** the API answers 503 `openbao_not_configured` listing `BAO_ADDR`
- **AND** no request is made to Substack and no file or variable is written

### Requirement: Browser Session Sync Never Discloses Cookie Values

No cookie value SHALL appear in a response body, a log record, an exception
message, an audit row, or the OpenAPI document. Cookie fields SHALL be documented as
`writeOnly` password-format strings without examples.

#### Scenario: Sentinel values
- **WHEN** requests carrying sentinel cookie values succeed, fail validation, or fail the OpenBao write
- **THEN** neither the responses, the captured logs, the audit rows nor `/openapi.json` contain any sentinel

### Requirement: Browser Session Sync Is Rate Limited

The API SHALL allow at most 10 browser-session sync calls per client IP in any
5-minute window and SHALL answer further calls with 429 and a `Retry-After` header.

#### Scenario: Looping client
- **WHEN** a client exceeds the window's allowance
- **THEN** the API answers 429 with `Retry-After` and makes no request to the site or OpenBao
