# Contract assessment

This change does not add or modify an HTTP endpoint, database schema, event
payload, or generated model. The canonical workflow OpenAPI remains:

`openspec/contracts/content-workflows/openapi/v1.yaml`

The implementation changes how the existing client serializes optional query
parameters and how the CLI separates JSON payloads from diagnostics. Tests
therefore validate actual `httpx` request URLs against the existing optional
cursor contract rather than introducing a duplicate contract file.
