## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2024-05-23 - Mitigation of Exception Data Leakage into Database Fields
**Vulnerability:** Across various processor, service, and API endpoints, raw exception details (e.g. `str(e)`) were being written directly into database fields, like `error_message`.
**Learning:** Hardcoded assignments of generic exception string representations to database columns inadvertently expose internal stack trace snippets, database connection strings, or system paths, leaking sensitive infrastructure data if displayed in user-facing endpoints.
**Prevention:** Always replace raw error assignments with generic, safe failure messages (e.g., "An internal error occurred during processing.") and log the actual sensitive exceptions securely on the server side using the logger mechanism.
