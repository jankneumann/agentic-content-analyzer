# Reconciliation contracts

This change adds one canonical HTTP operation-control surface. The source
OpenAPI contract remains `openspec/contracts/content-workflows/openapi/v1.yaml`;
implementation updates that file and regenerates Python and TypeScript models.

`reconciliation-report.schema.json` is the planning boundary for the bounded
request and safe report projection. Contract tests must prove its request/report
definitions remain structurally equivalent to canonical OpenAPI schemas. It
intentionally contains no content text, title, URL, operation input, result,
checkpoint, or raw error fields.

No event contract is added: RI-09 will consume the stable action and reason codes
after RI-08 establishes their durable audit projection. `db/schema.sql` records
the exact additive database boundary mirrored by Alembic and queue bootstrap.
