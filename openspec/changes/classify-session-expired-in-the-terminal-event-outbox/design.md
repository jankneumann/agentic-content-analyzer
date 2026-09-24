# Design: Classify session_expired in the terminal-event outbox

## Decision 1: severity follows the existing outcome convention

A credential failure is not given its own severity. The outbox already maps
`failed -> error` and `partial | zero_items | unknown | reconciled -> warning`,
and `WorkflowAlertEnvelopeV1` enforces that mapping for operation alerts.

- `session_expired` and `credentials_missing` for Substack (paid-only, fail
  closed since ri-18) and X fail the operation, so they alert as **error**. That
  is right: every scheduled run ingests nothing until the operator acts.
- A completed run that only *warns* about a credential (outcome `zero_items` or
  `partial`) alerts as **warning** and still carries the command.

## Decision 2: an optional closed `remediation_command` field, not free text

The envelope is allowlist-first with no free text. The command is added as a
closed literal, not as a message, so no source-derived string can reach an
external sink through it. It is omitted when absent, using the serializer
precedent of `release_revision`, so existing receivers and the redaction
property test see byte-identical bodies for every other alert. The model and
the schema both reject it unless the alert is an `ingestion.execute` operation
alert whose codes contain a credential code.

The command is looked up from the persisted `command_key`
(`substack -> aca auth session substack`, `x_bookmarks -> aca auth session x`),
never parsed from a diagnostic message.

## Decision 3: failed ingestion alerts read the attached result

The handler writes the sanitized result before it raises. The classifier now
reads that result for a failed `ingestion.execute` and appends its safe codes
after `operation_failed`. An invalid or missing result keeps the historical
`("operation_failed",)`, and non-ingestion operations are unchanged.

## Decision 4: credential alerts bypass pipeline aggregation

The pipeline root's alert summarizes per-source outcomes without codes, so
suppressing the child would lose the command. A classification that carries a
`remediation_command` is routed immediately. This can produce two alerts for one
pipeline run: the root's `partial`, and the child's actionable one. Delivery
stays once per event per sink through the existing
`(event_id, sink_name)` uniqueness.

## Non-goals

- The outbox, sinks, and delivery machinery are unchanged.
- The unrelated drift between `workflow-alert-envelope.schema.json` and the
  model (Obsidian and backup codes, `system_check`) is left for its owner.
