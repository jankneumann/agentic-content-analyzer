## ADDED Requirements

### Requirement: Credential failure alerts name the refresh command

The terminal-event outbox SHALL classify a credential-gated ingestion that
fails with `session_expired` or `credentials_missing` as an externally routed
alert whose `codes` include that code. Severity SHALL follow the outcome: `error`
for a failed operation and `warning` for a completed run that only warns. The
envelope SHALL carry `remediation_command`, drawn from the closed set
`aca auth session substack` and `aca auth session x` and looked up from the
persisted ingestion `command_key`. The envelope SHALL NOT contain a credential
value or credential-derived text. It SHALL omit `remediation_command` for every
alert that names no credential failure. A credential alert for a pipeline child
SHALL be routed on its own and not suppressed by the pipeline root.

#### Scenario: A dead Substack session produces one actionable error alert

- **WHEN** a Substack ingestion fails closed with `session_expired` and the worker alert tick runs twice
- **THEN** the webhook receives exactly one envelope with severity `error`, codes `operation_failed` and `session_expired`, and `remediation_command` `aca auth session substack`
- **AND** the envelope contains neither the cookie value nor the credential label
- **AND** the real telemetry emitter checkpoints `telemetry_emitted_at`

#### Scenario: The alert's diagnostic URL resolves

- **WHEN** an operator follows the `diagnostic_url` of a credential failure alert and reads the matching terminal-event diagnostic
- **THEN** both routes answer 200 with the failed operation and its `session_expired` result code

#### Scenario: A credential failure inside the scheduled pipeline is not swallowed

- **WHEN** a failed Substack child ingestion carries `session_expired` while its pipeline root is running, failed, or completed
- **THEN** the child alert is routed immediately and is not deferred or suppressed

#### Scenario: Other alerts are unchanged

- **WHEN** an alert names no credential failure
- **THEN** its envelope carries no `remediation_command` field
- **AND** the model and schema reject a `remediation_command` on any other alert
