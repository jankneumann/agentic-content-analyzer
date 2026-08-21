# Contracts — add-gx10-backup-scheme

Sub-types evaluated:

| Sub-type | Applicable | Notes |
|---|---|---|
| OpenAPI | **No** | No endpoint is added. `/ready` gains no new response *shape* — `checks` remains a flat `dict[str, str]` and `checks["backup"]` remains a status string. Only the derivation of that string changes. |
| Database | **No** | No schema change. Backup state lives in the backup target, not in Postgres — deliberately, so it survives loss of the database (design D7). |
| Events | **Yes** | `events/backup-freshness-alert.schema.json` — the widened alert envelope shape for the `system_check` source. |
| Data artifacts | **Yes** | `schemas/backup-manifest.schema.json` — the manifest object written to the backup target. It is the coordination boundary between the backup writer and every freshness reader, so it is contracted rather than implied. |
| Type generation | **No** | No frontend consumer. |
