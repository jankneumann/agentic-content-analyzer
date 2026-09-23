## ADDED Requirements

### Requirement: Auth Status Reports Browser Sessions

`aca auth status` SHALL print, after the OAuth providers, one row per browser
session: `substack` (credential `SUBSTACK_SESSION_COOKIE`) and `x` (credentials
`X_AUTH_TOKEN` and `X_CT0`). Each row SHALL report whether the session is present,
where its credentials resolved from (`openbao`, `env`, or `settings`; `mixed` when
the parts differ), `saved_at`, `last_verified_at`, and the refresh command
`aca auth session substack` or `aca auth session x`. The `x` session SHALL be
present only when both of its credentials are present, and its `saved_at` SHALL be
the older of the two `<KEY>_SAVED_AT` values. Presence, source and `saved_at` SHALL
come from the live credential provider's metadata. Neither output mode SHALL ever
contain a credential value.

#### Scenario: Substack session saved through OpenBao
- **WHEN** OpenBao holds `SUBSTACK_SESSION_COOKIE` with `SUBSTACK_SESSION_COOKIE_SAVED_AT=2026-09-01T10:00:00Z`
- **THEN** the `substack` row is present with source `openbao`, `saved_at` `2026-09-01T10:00:00Z`, and refresh command `aca auth session substack`
- **AND** the cookie value appears nowhere in stdout or stderr

#### Scenario: X session with only one of its two cookies
- **WHEN** `X_AUTH_TOKEN` is present and `X_CT0` is absent
- **THEN** the `x` row is missing and lists `X_AUTH_TOKEN` present and `X_CT0` missing

#### Scenario: Credential supplied by a process environment variable
- **WHEN** `SUBSTACK_SESSION_COOKIE` is not in OpenBao but is set in the process environment
- **THEN** the `substack` row reports source `env` and `saved_at` unknown

### Requirement: Durable Last Verified Time

`last_verified_at` for a browser session SHALL be the completion time of the most
recent terminal ingestion of the source that session gates (`substack` for
`substack`, `x_bookmarks` for `x`) whose outcome is `success` or `zero_items`, read
from the durable ingestion history in `pgqueuer_jobs`. The lookup SHALL go to
`/api/v1/ingestions` under a remote profile and to the queue database otherwise,
SHALL be bounded by a short timeout, and SHALL NOT fail the command: when the
history cannot be read, `last_verified_at` SHALL be reported as unknown with a
diagnostic naming only the error type. A source with no successful ingestion, or a
source kind that does not exist yet, SHALL be reported as never verified.

#### Scenario: Latest successful run wins
- **WHEN** the history holds a `substack` run that succeeded on 2026-09-18, a `zero_items` run on 2026-09-19, and a `partial` run on 2026-09-20
- **THEN** the `substack` row reports `last_verified_at` `2026-09-19`

#### Scenario: Database unreachable
- **WHEN** the queue database refuses the connection
- **THEN** `aca auth status` exits 0, both rows report `last_verified_at` unknown, and stderr names `ConnectionRefusedError`

#### Scenario: Source kind not yet ingested
- **WHEN** no `x_bookmarks` ingestion has ever completed
- **THEN** the `x` row reports `last_verified_at` as never verified rather than an error

#### Scenario: Verification older than the saved credential
- **WHEN** `saved_at` is later than `last_verified_at`
- **THEN** the text output marks the session as not yet verified since the last save

### Requirement: Auth Status JSON Output

`aca auth status --json` (and the global `aca --json auth status`) SHALL write
exactly one JSON document to stdout with the keys `oauth`, `browser_sessions`, and
`last_verified_lookup`, and SHALL write diagnostics only to stderr. Each
`browser_sessions` entry SHALL carry `session`, `present`, `source`, `saved_at`,
`last_verified_at`, `last_verified_status` (`verified`, `never`, or `unknown`),
`verified_by`, `refresh_command`, and per-credential `credentials` entries holding
names, labels, presence, source and `saved_at` only. OAuth entries SHALL report
Railway variables as booleans, never the listing the Railway CLI returns.

#### Scenario: JSON is one document without values
- **WHEN** `aca auth status --json` runs with sentinel values in OpenBao and in the Railway variable listing
- **THEN** stdout parses as a single JSON object listing `substack` and `x` with `saved_at`, `last_verified_at`, and `refresh_command`
- **AND** no sentinel value appears in stdout or stderr
