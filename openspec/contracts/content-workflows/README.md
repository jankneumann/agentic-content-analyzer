# Content Workflow Contracts

This directory is the durable source of truth for executable content workflow contracts.
Active generators, tests, backend models, and frontend types consume these files directly.
Copies under `openspec/changes/archive/` are historical snapshots and MUST NOT be used as
generation inputs.

- `openapi/v1.yaml` defines the coordinated breaking HTTP contract, source command discriminator, operations, problems, uploads, and capability discovery.
- `db/schema.sql` defines additive provenance storage and the versioned queue payload boundary.
- `db/seed.sql` provides deterministic canonical/alias/null-date and operation fixtures.
- `events/operation.progress.schema.json` defines progress events used by SSE and frontend clients.
- `generated/models.py` and `generated/types.ts` are deterministic outputs of `scripts/generate_workflow_contracts.py` and SHALL NOT be edited independently.

Run `make workflow-contracts` after changing the OpenAPI or event contract. The command uses the declared development toolchain so generated Python is Ruff-formatted deterministically. CI runs `make workflow-contracts-check` to validate both schemas and reject generated-file drift.

The API remains mounted under `/api/v1` for this coordinated cutover, while `info.version: 2.0.0` identifies the replacement contract. All controlled clients must deploy with the backend release.
