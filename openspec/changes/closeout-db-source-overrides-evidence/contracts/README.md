# Contract delta

This change adds source management to the existing durable
`openspec/contracts/content-workflows/openapi/v1.yaml` contract:

- `GET /api/v1/sources`
- `POST /api/v1/sources`
- `PATCH /api/v1/sources/{key}`
- `DELETE /api/v1/sources/{key}`

POST has one meaningful discriminator at `config.type`; PATCH mutates only
`enabled`. Existing `/api/v1` behavior ignores unknown request siblings, which
must have no semantic effect. The contract records owner-session and
`X-Admin-Key` authentication; operation-specific success projections; legacy
service, validation, and auth error bodies; versioning; origin; and Obsidian's
privacy-safe opaque key.

The existing generator produces Python and TypeScript contract models/types.
It does not generate HTTP clients. Contract and transport tests must prove that
the FastAPI implementation and hand-maintained CLI/web wrappers stay aligned
with those generated types.

The archived source-change contract is historical evidence and intentionally
remains untouched. Its redundant top-level `type` and obsolete mutation paths
must not be copied into the durable contract.

The change also carries a targeted `MODIFIED` delta for the durable
`source-configuration` management API/CLI requirements. It distinguishes the
internal natural key from the public management key, requires opaque Obsidian
identity, and clarifies that disabled shadows remain management-visible while
ingestion selection excludes them.
