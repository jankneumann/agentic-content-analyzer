# Contract delta

This change adds source management to the existing durable
`openspec/contracts/content-workflows/openapi/v1.yaml` contract:

- `GET /api/v1/sources`
- `POST /api/v1/sources`
- `PATCH /api/v1/sources/{key}`
- `DELETE /api/v1/sources/{key}`

POST has one discriminator at `config.type`; PATCH accepts only `{enabled}`.
The contract records owner-session and `X-Admin-Key` authentication, stable
response/error shapes, versioning, origin, and privacy-safe opaque keys for
private sources.

The existing generator produces Python and TypeScript contract models/types.
It does not generate HTTP clients. Contract and transport tests must prove that
the FastAPI implementation and hand-maintained CLI/web wrappers stay aligned
with those generated types.

The archived source-change contract is historical evidence and intentionally
remains untouched. Its redundant top-level `type` and obsolete mutation paths
must not be copied into the durable contract.
