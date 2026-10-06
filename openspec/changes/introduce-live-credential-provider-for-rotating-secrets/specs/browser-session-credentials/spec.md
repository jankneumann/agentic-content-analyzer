## ADDED Requirements

### Requirement: Live Credential Provider

The system SHALL provide a `CredentialProvider` that resolves the browser-session
credentials `SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, and `X_CT0` at call time,
consulting the in-memory OpenBao cache first and the `Settings` fields
`substack_session_cookie`, `x_auth_token`, and `x_ct0` second. The mapping between
each credential name and its `Settings` field SHALL be explicit, and an unregistered
name SHALL be refused. Resolving a credential SHALL NOT perform network I/O once the
OpenBao cache has loaded, and an empty value SHALL be treated as absent.

#### Scenario: Rotated cookie reaches a long-running worker without restart
- **WHEN** a worker process has resolved `SUBSTACK_SESSION_COOKIE` from OpenBao, the KV secret is then patched with a new cookie, and the AppRole token manager performs one refresh
- **THEN** the next `get("SUBSTACK_SESSION_COOKIE")` in the same process returns the new cookie
- **AND** no new `Settings` instance was built

#### Scenario: Settings fallback without OpenBao
- **WHEN** `BAO_ADDR` is unset and `Settings.x_ct0` holds a value
- **THEN** `get("X_CT0")` returns that value and `metadata("X_CT0").source` is `settings`

#### Scenario: Unregistered credential name
- **WHEN** a caller asks for `ANTHROPIC_API_KEY`
- **THEN** the provider raises `UnknownCredentialError`

### Requirement: Credential Metadata Without Values

The provider SHALL expose, for each registered credential, whether it is present,
where it resolved from, `saved_at` parsed from the `<NAME>_SAVED_AT` OpenBao sibling
key (absent or unparseable yields none), and `last_verified_at`. The metadata SHALL
never contain the credential value. `last_verified_at` SHALL be recorded in process
memory only, SHALL apply only while the verified value is still current, and SHALL
NOT cause any write to OpenBao.

#### Scenario: saved_at for every browser session
- **WHEN** OpenBao holds `SUBSTACK_SESSION_COOKIE` with `SUBSTACK_SESSION_COOKIE_SAVED_AT=2026-09-01T10:00:00Z`
- **THEN** `metadata` returns `saved_at` 2026-09-01 10:00 UTC with label `substack.sid`
- **AND** `metadata` for `X_AUTH_TOKEN` and `X_CT0` returns labels `x.auth_token` and `x.ct0` with `saved_at` none when no sibling exists

#### Scenario: Verification is cleared by rotation
- **WHEN** `mark_verified("SUBSTACK_SESSION_COOKIE")` is called and the cookie is later rotated in OpenBao and refreshed
- **THEN** `metadata("SUBSTACK_SESSION_COOKIE").last_verified_at` is none
- **AND** no PATCH or write was sent to OpenBao to record the verification

### Requirement: Credential Values Never Logged

Credential resolution, refresh, and local write-back SHALL log credential names and
counts only. The `Settings` fields for browser-session credentials SHALL be excluded
from `repr`, and secret-key detection used for masking SHALL match
`SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, and `X_CT0`.

#### Scenario: Provider tests capture no value
- **WHEN** the provider loads, refreshes, applies a local write, and falls back to settings with DEBUG logging captured
- **THEN** no captured log record contains any credential value

#### Scenario: Settings repr hides the cookies
- **WHEN** a `Settings` instance holding all three browser-session credentials is rendered with `repr`
- **THEN** none of the three values appears in the output

### Requirement: Substack Adapter Uses the Live Provider

The Substack adapter SHALL resolve the `substack.sid` cookie through the credential
provider before every HTTP request unless an explicit session cookie was passed to
it, and SHALL NOT read `settings.substack_session_cookie` directly.

#### Scenario: Cookie rotated between two requests
- **WHEN** a `SubstackClient` sends one request, the cookie is rotated in OpenBao and the provider refreshes, and the same client sends a second request
- **THEN** the first request carries the old `substack.sid` and the second carries the new one
- **AND** each request carries exactly one `substack.sid`

#### Scenario: Explicit override wins
- **WHEN** a `SubstackClient` is created with an explicit `session_cookie`
- **THEN** its requests carry that cookie regardless of OpenBao or `Settings`
