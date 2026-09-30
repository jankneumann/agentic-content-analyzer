## ADDED Requirements

### Requirement: Browser-Session Credentials Are Allowlisted For Railway

The shipped allowlist `settings/deploy/railway_secrets.yaml` SHALL list
`SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, and `X_CT0` for the `api` service, and the
`worker` service SHALL inherit them through `extends: api`, so `aca deploy
sync-secrets` can push browser-session credentials until workers read them from
OpenBao.

#### Scenario: Shipped allowlist carries session credentials
- **WHEN** the shipped allowlist is loaded
- **THEN** both the `api` and `worker` services include `SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, and `X_CT0`
