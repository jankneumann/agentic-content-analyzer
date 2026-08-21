# Contracts — add-gx10-backup-scheme

Sub-types evaluated:

| Sub-type | Applicable | Notes |
|---|---|---|
| OpenAPI | **No** | No endpoint is added. `/ready` gains no new response *shape* — `checks` remains a flat `dict[str, str]` and `checks["backup"]` remains a status string. Only the derivation of that string changes. |
| Database | **No** | No schema change. Backup state lives in the backup target, not in Postgres — deliberately, so it survives loss of the database (design D7). |
| Events | **Yes** | `events/backup-freshness-alert.schema.json` — the widened alert envelope shape for the `system_check` source. |
| Data artifacts | **Yes** | `schemas/backup-manifest.schema.json` — the manifest object written to the backup target. It is the coordination boundary between the backup writer and every freshness reader, so it is contracted rather than implied. |
| Type generation | **No** | No frontend consumer. |

## Durable landing locations

Files here are planning artifacts. `openspec/contracts/README.md` states that live
code, generators, and tests MUST NOT depend on anything under `openspec/changes/`,
so implementation lands each schema in the durable tree:

| Planning artifact | Durable location | Task |
|---|---|---|
| `schemas/backup-manifest.schema.json` | `openspec/contracts/backup/schemas/` — a new domain, registered in `openspec/contracts/README.md` | 0.1, 0.3 |
| `events/backup-freshness-alert.schema.json` | `openspec/contracts/content-workflows/events/` | 0.2 |

The alert schema lands in `content-workflows`, **not** in the new `backup` domain,
because it describes one variant of `WorkflowAlertEnvelopeV1` — an envelope that
already belongs to that domain. Splitting one envelope's shape across two domains
would leave no single place to look for it.

## Drift risk on the alert schema

`WorkflowAlertEnvelopeV1` (`src/contracts/workflow_alert_models.py`) is
hand-written, not generated — the `contracts.generated.pydantic_dir: src/contracts`
entry in `work-packages.yaml` records where generated Pydantic *would* live for
domains that have a generator, and the alert envelope is not one of them. Adding a
JSON Schema for it therefore creates a second hand-maintained description of one
shape, with nothing forcing the two to agree.

Task 0.2 closes that with a conformance test asserting the schema and the model
agree, so the drift is caught by the suite rather than by an undelivered alert.


## Revised after PLAN_REVIEW

| Sub-type | Was | Now |
|---|---|---|
| OpenAPI | No | **Still No.** The alert's `diagnostic_url` reuses `/api/v1/workflow-terminal-events/{event_id}`, which already exists and is already in `validate_diagnostic_route`'s allowlist. The earlier draft pinned it to `/api/v1/health/backup` — a route that does not exist and that no task created, while this file simultaneously claimed no endpoint was added. Reusing the existing route keeps that claim true. |
| Database | No | **Yes — a migration is now in scope.** Not for backup state, which still lives in the backup target, but for alert delivery: `workflow_terminal_events` enforces three CHECK constraints that reject a `system_check` row. See design A1. |
