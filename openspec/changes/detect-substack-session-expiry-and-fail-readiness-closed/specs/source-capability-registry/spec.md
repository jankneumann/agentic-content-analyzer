## ADDED Requirements

### Requirement: Credential-Gated Source Readiness

A source descriptor whose adapter depends on a browser-session credential SHALL
resolve readiness through the live `CredentialProvider`, never through
`Settings`. The `substack` descriptor SHALL report `ready=false` with code
`credentials_missing` when `SUBSTACK_SESSION_COOKIE` is absent, `ready=false`
with code `session_expired` while the current cookie is recorded as rejected, and
`ready=true` otherwise.

#### Scenario: Missing cookie
- **WHEN** neither OpenBao nor `Settings` holds `SUBSTACK_SESSION_COOKIE`
- **THEN** the `substack` descriptor reports `ready=false` with code `credentials_missing`

#### Scenario: Expired session flips back without restart
- **WHEN** the adapter recorded the current cookie as rejected and the descriptor reports `session_expired`, and a fresh cookie is then patched into the OpenBao cache
- **THEN** the same process reports `ready=true` for the `substack` descriptor with no restart
