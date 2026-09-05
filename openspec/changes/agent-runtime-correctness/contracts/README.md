# Contracts: agent-runtime-correctness

| Sub-type | Applies | Artifact |
|---|---|---|
| OpenAPI | Yes | `openapi/v1.yaml` (delta against `openspec/contracts/content-workflows/openapi/v1.yaml`) |
| Database | Yes | `db/schema.sql` (two Alembic migrations) |
| Events | No | No new event payloads. `OperationEvent` gains only the two new `operation_type` enum members already covered by the OpenAPI delta. |
| Generated types | Via `make workflow-contracts` | `src/contracts/workflow_models.py`, `web/src/generated/workflow-contracts.ts` are regenerated, never hand-edited |

Merge rule: `wp-contracts` folds the delta into the canonical file and regenerates. The
`OperationTypeDelta` schema is not itself added to the canonical file; its members are
appended to each existing `operation_type` enum copy.
