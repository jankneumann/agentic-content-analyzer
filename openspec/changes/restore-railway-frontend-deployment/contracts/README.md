# Contract assessment

This change does not modify the canonical workflow OpenAPI:

`openspec/contracts/content-workflows/openapi/v1.yaml`

The deployed frontend already consumes the generated `CapabilityDocument`,
`IngestCommand`, and durable operation models. The release change moves drift
verification into CI with the full generator toolchain and makes the Railway
artifact build consume those checked-in generated models without running the
generator inside the isolated static-site image.
