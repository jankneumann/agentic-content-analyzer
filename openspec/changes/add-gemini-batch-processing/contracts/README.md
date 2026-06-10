# Contracts — Gemini Batch Execution

Contract sub-types evaluated for this change:

| Sub-type | Applies? | Artifact |
|----------|----------|----------|
| Database | ✅ Yes | `db/schema.sql` — `batch_jobs`, `batch_requests`, and the Phase-3 `PENDING_BATCH` enum value |
| OpenAPI | ❌ No | No HTTP API surface. The new CLI commands (`aca evaluate batch-savings`, `aca batch ...`) call services in-process. |
| Events | ❌ No | Reuses the existing `NotificationEventType.BATCH_SUMMARY` event; no new event payload schema. |
| Type stubs | ❌ No | Internal dataclasses (`BatchRequest`, `BatchPollResult`) defined in code, not generated from a contract. |

The DB schema is the coordination boundary: the migration (task 0.1.1), the
SQLAlchemy models (0.1.2), and the workers (0.4.x) all assert against it.
