# Backup Contracts

Durable contracts for the off-site backup scheme (`aca backup`, the freshness check,
and the durable freshness alert).

## Files

| File | Owner | Purpose |
|---|---|---|
| `schemas/backup-manifest.schema.json` | `src/services/backup/` | The bucket-side run manifest. Authoritative record of backup freshness — the check reads this, never `cron.job_run_details`. |
| `events/backup-freshness-alert.schema.json` | `src/contracts/workflow_alert_models.py` | The `system_check` narrowing of `WorkflowAlertEnvelopeV1`, and the single source of truth for the backup diagnostic-code set. |

## Maintenance

Both schemas are pinned by `tests/contract/test_backup_contracts.py`:

- The manifest schema is checked against valid and invalid instances, including the
  conditional `if/then` requirements that make an empty upload distinguishable from a
  good one.
- The alert schema is checked for **narrowing-compatibility** against
  `WorkflowAlertEnvelopeV1` — not field equality. The schema is deliberately a narrowed
  variant (constants and subsets) in several places. What the test enforces is that no
  schema field is absent from the model, no model field is absent from the schema, the
  required sets are identical, and every instance the schema accepts the model also
  accepts.

The diagnostic-code enum lives here and nowhere else. Design prose and task lists
reference this file rather than restating the set; the set drifted three times while it
was enumerated in three places.

## Two invariants worth stating plainly

1. **The manifest is the only unencrypted object on the backup target.** It exists so a
   freshness reader that holds no decryption identity can still evaluate freshness. That
   is why it must never carry a credential, and why `reason` is a closed lowercase token
   rather than a subprocess stderr body.
2. **A document describing a constraint is not the code enforcing it.** These schemas do
   not widen the model; the model in `src/contracts/workflow_alert_models.py` and the
   emitting service in `src/services/workflow_terminal_event_service.py` do. The
   conformance tests exist to make disagreement between them fail loudly.
