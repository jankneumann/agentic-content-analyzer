## ADDED Requirements

### Requirement: Multi-credential live-adapter policy

The live-adapter policy SHALL let a source require all of its credential
environment variables instead of any one of them. The `x_bookmarks` policy
SHALL be live-eligible and SHALL require both `X_AUTH_TOKEN` and `X_CT0`; every
other credentialed source SHALL keep any-of semantics. A skip reason SHALL name
the required variables joined with "and" for an all-of policy.

#### Scenario: Half a session skips the live run

- **WHEN** the scheduled tier evaluates `x_bookmarks` with only `X_AUTH_TOKEN` set
- **THEN** the decision is `skip_missing_credential` with reason `Skipped: missing credential (X_AUTH_TOKEN and X_CT0)`

#### Scenario: Full session runs live

- **WHEN** both `X_AUTH_TOKEN` and `X_CT0` are set and live execution is enabled
- **THEN** the decision is `live`
