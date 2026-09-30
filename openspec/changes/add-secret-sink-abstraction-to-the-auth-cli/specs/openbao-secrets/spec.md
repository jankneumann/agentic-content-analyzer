## ADDED Requirements

### Requirement: CLI Secret Sink Writes Use Server-Side KV v2 PATCH

The OpenBao secret sink (`aca auth <provider> --to bao`) SHALL write secrets to the
existing KV v2 secret at `BAO_MOUNT_PATH`/`BAO_SECRET_PATH` (default
`secret/newsletter`) with a single server-side HTTP `PATCH` using
`application/merge-patch+json`. It SHALL NOT call `create_or_update_secret`, SHALL NOT
use hvac's client-side `kv.v2.patch()` (a read followed by a full write), and SHALL NOT
need `read` capability on the path. For every written key `K` the same PATCH SHALL
record a sibling `K_SAVED_AT` holding the write time as an ISO-8601 UTC timestamp.

#### Scenario: Single-key write leaves sibling keys byte-identical
- **WHEN** `aca auth gmail --to bao` completes against a KV v2 secret that already holds `ANTHROPIC_API_KEY` and other keys
- **THEN** exactly one PATCH is sent to `/v1/secret/data/newsletter`
- **AND** its body contains only `GMAIL_OAUTH_TOKEN_JSON` and `GMAIL_OAUTH_TOKEN_JSON_SAVED_AT`
- **AND** every other key at the path is byte-identical to its value before the write

#### Scenario: Several keys land in one atomic patch
- **WHEN** a caller writes `X_AUTH_TOKEN` and `X_CT0` through the sink in one call
- **THEN** one PATCH carries both keys and both `_SAVED_AT` siblings

#### Scenario: Missing secret path is not created
- **WHEN** the PATCH target does not exist and OpenBao answers 404
- **THEN** the command exits non-zero with a message that the path does not exist and must be seeded first
- **AND** no write that could create the path is attempted

#### Scenario: Insufficient capability is explained
- **WHEN** OpenBao answers 403 to the PATCH
- **THEN** the command exits non-zero with a message naming the missing `patch` capability

### Requirement: CLI Secret Sink Fails Fast Without OpenBao

The OpenBao sink SHALL validate its configuration and authenticate before the
interactive OAuth flow starts, and SHALL exit non-zero with an actionable message when
`BAO_ADDR` is unset, when no AppRole or token credentials are set, when the optional
`hvac` dependency is not installed (naming `pip install '.[vault]'`), or when
authentication fails.

#### Scenario: BAO_ADDR unset
- **WHEN** `aca auth gmail --to bao` runs without `BAO_ADDR`
- **THEN** the command exits 1 naming `BAO_ADDR`
- **AND** the OAuth browser flow is never started

#### Scenario: hvac not installed
- **WHEN** `BAO_ADDR` and `BAO_TOKEN` are set but `hvac` is not importable
- **THEN** the sink reports that `.[vault]` must be installed
