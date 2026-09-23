## ADDED Requirements

### Requirement: Browser Session Capture Command

The CLI SHALL provide `aca auth session substack` and `aca auth session x`, each
accepting `--to bao|railway|secrets-file`, `--timeout SECONDS` (default 300) and
`--headless`. The command SHALL launch Chromium through Playwright
`launch_persistent_context` on the per-site profile directory
`browser_profiles_dir()/<site>`, headed unless `--headless` is given, and SHALL
create that directory and the profiles root with mode 0700. It SHALL refuse a
profile directory that is a symlink. It SHALL capture `substack.sid` on
`substack.com` for Substack, and both `auth_token` and `ct0` on `x.com` for X,
falling back to `twitter.com` only when `x.com` does not hold both, and SHALL never
combine cookies from two domains. When `--to` is omitted the sink SHALL be `bao` if
`BAO_ADDR` is set and `secrets-file` otherwise.

#### Scenario: Profile already holds a valid session
- **WHEN** the persisted profile already contains the site's target cookies and the validation request succeeds
- **THEN** the command writes them without opening the login page or waiting for user input
- **AND** a second run against the same profile directory again needs no login

#### Scenario: Login never completes
- **WHEN** the browser context never produces the target cookies within `--timeout` seconds
- **THEN** the command exits non-zero with a message naming the missing cookies and the timeout
- **AND** nothing is written to any sink

#### Scenario: X needs both cookies
- **WHEN** the X profile holds `auth_token` but no `ct0`
- **THEN** the command keeps waiting and times out without writing

#### Scenario: Profile directory permissions
- **WHEN** the command runs for `substack` and the profiles root already exists with mode 0755
- **THEN** `browser_profiles_dir()/substack` exists with mode 0700 and the root is tightened to 0700

### Requirement: Session Validation Before Write

Before writing, the command SHALL make exactly one authenticated request with
httpx, not through the browser: `GET https://substack.com/api/v1/subscriptions`
with the `substack.sid` cookie, or `GET https://x.com/i/api/1.1/account/settings.json`
with the public X web bearer token, the `auth_token` and `ct0` cookies and an
`x-csrf-token` header equal to `ct0`. Redirects SHALL NOT be followed. Any response
other than HTTP 200 with the expected JSON, or a transport error, SHALL exit
non-zero and SHALL NOT write to the sink.

#### Scenario: Rejected session
- **WHEN** the validation request returns HTTP 401, an HTML login page, or JSON without the expected fields
- **THEN** the command exits non-zero and the sink receives no write

### Requirement: Single Atomic Sink Write Without Echoing Values

After successful validation the command SHALL write the site's credentials in one
`SecretSink.write()` call: `{SUBSTACK_SESSION_COOKIE}` for Substack and
`{X_AUTH_TOKEN, X_CT0}` for X. After a `bao` write it SHALL apply the same values
to the in-process credential provider with the `saved_at` the sink recorded. No
cookie value SHALL appear on stdout, stderr, in logs, in process arguments, or in
an exception message; output SHALL name only cookies, domains, keys and the sink
target. The command SHALL NOT create any refresh timer, cron entry or scheduled job.

#### Scenario: Stubbed context patches OpenBao once
- **WHEN** `aca auth session x --to bao` runs against a context that already holds both cookies and validation succeeds
- **THEN** OpenBao receives exactly one KV v2 PATCH carrying `X_AUTH_TOKEN`, `X_CT0` and matching `_SAVED_AT` siblings
- **AND** the credential provider receives the same values stamped with the same `saved_at`
- **AND** neither cookie value appears in the command output or the captured logs

### Requirement: Setup Guide Uses the Capture Command

`docs/SETUP.md` SHALL present `aca auth session substack` as the way to capture the
Substack session cookie, and SHALL keep the DevTools steps only as a manual fallback.

#### Scenario: Substack setup instructions
- **WHEN** an operator reads "Substack API Setup" in `docs/SETUP.md`
- **THEN** step 1 shows `aca auth session substack` with its sink options
- **AND** the DevTools copy steps appear only under a manual-fallback note
