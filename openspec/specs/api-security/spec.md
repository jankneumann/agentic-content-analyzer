# api-security Specification

## Purpose
TBD - created by archiving change add-api-security-hardening. Update Purpose after archive.
## Requirements
### Requirement: Authenticated access for protected APIs
The system SHALL require authenticated access for non-public API endpoints in production environments.

#### Scenario: Production request without credentials
- **WHEN** a client calls a protected endpoint without valid credentials in production
- **THEN** the API returns a 401 Unauthorized response

#### Scenario: Production request with valid credentials
- **WHEN** a client calls a protected endpoint with valid credentials in production
- **THEN** the API returns the requested resource

#### Scenario: Development request without credentials
- **WHEN** a client calls a protected endpoint without credentials in development mode
- **THEN** the API allows access without authentication (dev-mode bypass)

#### Scenario: Development request with invalid credentials
- **WHEN** a client provides an invalid API key in development mode
- **THEN** the API returns a 403 Forbidden response (explicit keys are always validated)

### Requirement: Production security configuration validation
The system SHALL validate security-critical configuration at startup in production environments.

#### Scenario: Production startup without ADMIN_API_KEY
- **WHEN** the application starts with `ENVIRONMENT=production` and `ADMIN_API_KEY` is not set
- **THEN** the system logs a security warning identifying the missing configuration

#### Scenario: Production startup with dev-default CORS origins
- **WHEN** the application starts with `ENVIRONMENT=production` and `ALLOWED_ORIGINS` contains only localhost origins
- **THEN** the system logs a security warning about permissive CORS defaults

#### Scenario: Production startup with valid security configuration
- **WHEN** the application starts with `ENVIRONMENT=production`, `ADMIN_API_KEY` is set, and `ALLOWED_ORIGINS` contains explicit non-localhost origins
- **THEN** the system starts without security warnings

### Requirement: Environment-configured CORS policy
The system SHALL load allowed CORS origins from configuration and apply restrictive defaults in production.

#### Scenario: Production request without explicit CORS configuration
- **WHEN** a browser client makes a cross-origin request in production and no explicit `ALLOWED_ORIGINS` is configured
- **THEN** the API response does NOT include the `Access-Control-Allow-Origin` header (default deny)

#### Scenario: Production request from explicitly allowed origin
- **WHEN** a browser client makes a request from an origin in the configured `ALLOWED_ORIGINS` list in production
- **THEN** the API response includes `Access-Control-Allow-Origin` matching the request origin

#### Scenario: Development request from local origin
- **WHEN** a browser client makes a request from `http://localhost:5173` in development mode
- **THEN** the API response includes `Access-Control-Allow-Origin: http://localhost:5173`

#### Scenario: CORS preflight from allowed origin
- **WHEN** a browser sends an OPTIONS preflight request from an origin in the configured allowlist
- **THEN** the API responds with appropriate `Access-Control-Allow-*` headers and 200 status

### Requirement: Explicit public endpoint allowlist
The system SHALL maintain a documented list of endpoints that are intentionally accessible without authentication, distinguishing between system endpoints (health, config) and application endpoints (content, digests) that are unauthenticated due to the single-user deployment model.

#### Scenario: System endpoint listed as public
- **WHEN** a client calls a system endpoint listed in the public allowlist (e.g., `/health`, `/ready`, `/api/v1/system/config`)
- **THEN** the API returns the response without requiring authentication

#### Scenario: Application endpoint in single-user mode
- **WHEN** a client calls a content API endpoint (e.g., `/api/v1/content`, `/api/v1/digests`) without credentials
- **THEN** the API returns the response without requiring authentication (single-user model — instance is the security boundary)

#### Scenario: Protected endpoint without credentials in production
- **WHEN** a client calls a settings/admin endpoint (e.g., `/api/v1/settings/prompts`) without valid credentials in production
- **THEN** the API returns a 401 Unauthorized response

### Requirement: File upload signature validation
The system SHALL validate document uploads by checking file signatures (magic bytes) against the declared file extension.

#### Scenario: Upload with matching signature and extension
- **WHEN** a client uploads a file whose magic bytes match the declared extension (e.g., a `.pdf` file starting with `%PDF`)
- **THEN** the API accepts the upload for processing

#### Scenario: Upload with mismatched signature and extension
- **WHEN** a client uploads a file whose magic bytes do NOT match the declared extension (e.g., an executable renamed to `.pdf`)
- **THEN** the API rejects the upload with a 415 Unsupported Media Type response indicating signature mismatch

#### Scenario: Upload with unknown signature
- **WHEN** a client uploads a file with an extension that has no defined magic bytes mapping (e.g., `.txt`, `.md`)
- **THEN** the API skips signature validation and proceeds with extension-based format checking

### Requirement: Upload MIME type cross-check
The system SHALL validate that the client-provided MIME type is consistent with the declared file extension.

#### Scenario: Upload with consistent MIME type and extension
- **WHEN** a client uploads a file with MIME type `application/pdf` and extension `.pdf`
- **THEN** the API accepts the upload for processing

#### Scenario: Upload with contradictory MIME type and extension
- **WHEN** a client uploads a file with MIME type `image/png` but extension `.pdf`
- **THEN** the API rejects the upload with a 415 Unsupported Media Type response indicating type mismatch

#### Scenario: Upload with generic MIME type fallback
- **WHEN** a client uploads a file with MIME type `application/octet-stream` (browser/tool generic fallback)
- **THEN** the API skips MIME cross-check and proceeds with extension-based and signature-based validation only

### Requirement: Safe document upload size enforcement (existing)
The system SHALL validate document uploads with early size checks before full buffering.

#### Scenario: Upload exceeds configured size
- **WHEN** a client uploads a document larger than the configured limit
- **THEN** the API rejects the upload with a 413 Payload Too Large response without fully buffering the file

### Requirement: Sanitized error responses (existing)
The system SHALL avoid returning internal exception details in API error responses.

#### Scenario: Parser failure during upload
- **WHEN** a parsing exception occurs during upload processing
- **THEN** the API returns a generic error message without internal stack details or exception messages
