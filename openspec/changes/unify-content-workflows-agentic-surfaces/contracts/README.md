# Canonical Workflow Contracts

- `openapi/v1.yaml` defines the coordinated breaking HTTP contract, source command discriminator, operations, problems, uploads, and capability discovery.
- `db/schema.sql` defines additive provenance storage and the versioned queue payload boundary.
- `db/seed.sql` provides deterministic canonical/alias/null-date and operation fixtures.
- `events/operation.progress.schema.json` defines progress events used by SSE and frontend clients.
- `generated/models.py` and `generated/types.ts` are implementation stubs that SHALL be regenerated from the validated OpenAPI contract rather than maintained independently.

The API remains mounted under `/api/v1` for this coordinated cutover, while `info.version: 2.0.0` identifies the replacement contract. All controlled clients must deploy with the backend release.
