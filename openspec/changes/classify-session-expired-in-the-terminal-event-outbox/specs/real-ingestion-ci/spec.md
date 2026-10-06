## ADDED Requirements

### Requirement: Failure-class evidence records diagnostic codes

The failure-class evidence for each source SHALL record the closed diagnostic
codes from its durable ingestion result. The rendered summary SHALL show them,
and for `session_expired` or `credentials_missing` on a credential-gated source
it SHALL name the command that refreshes the session. Only codes from the public
diagnostic vocabulary SHALL be recorded, and no credential value SHALL appear.

#### Scenario: A dead Substack session is recorded with its code

- **WHEN** the Substack adapter fails closed with `session_expired` through the durable workflow and its evidence is rendered
- **THEN** the source row is classified `adapter` and shows `session_expired (refresh: `aca auth session substack`)`
- **AND** the summary does not contain the cookie value

#### Scenario: An ordinary failure offers no refresh command

- **WHEN** a failed source records only `fetch_error`
- **THEN** its row shows `fetch_error` and no `aca auth session` command
