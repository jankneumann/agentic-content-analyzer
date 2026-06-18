# Contracts — db-source-overrides

Coordination boundary between the parallel work packages.

| Sub-type | File | Consumed by |
|----------|------|-------------|
| Database | `db/schema.sql` | `wp-backend-data` (model + migration), test fixtures |
| OpenAPI  | `openapi/v1.yaml` | `wp-backend-api` (routes), `wp-cli` (api_client), `wp-web` (api module + types) |
| Events   | — | None evaluated; this feature emits no domain events |
| Types    | derived from `openapi/v1.yaml` | `wp-web` TypeScript interfaces (`SourceInfo`, `SourceMutationResult`) authored by hand to match |

The natural-key derivation (`<type>:<locator>`) is the implicit cross-cutting contract: a single `_source_key()` helper in `src/config/sources.py` is the authority and is referenced by the loader merge, the service, and the API/CLI/UI.
