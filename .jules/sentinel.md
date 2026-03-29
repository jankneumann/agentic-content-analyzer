## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2025-05-27 - Information Exposure in Global Error Handler
**Vulnerability:** The global error handlers `data_error_handler` and `asyncpg_data_error_handler` in `src/api/middleware/error_handler.py` were returning `exc.orig` and `exc` directly to the client in the 422 HTTP response detail field.
**Learning:** Returning raw database validation or asyncpg errors can expose sensitive internal details (e.g., query structure or internal systems state) to the end user.
**Prevention:** Global exception handlers should catch database and input errors but return sanitized generic strings like "Invalid parameter value" to the client.

## 2025-05-27 - Information Leakage via Database Fields
**Vulnerability:** The HTML processing service `src/services/html_processor.py` was catching `Exception` and saving the raw exception string (`str(e)[:1000]`) into the `content.error_message` database field.
**Learning:** Raw exception strings can leak internal system paths, environment variables, or other sensitive details. Saving them into a database field that is subsequently returned by an API (like `/formats` or `/upload` status endpoints) creates an information disclosure vulnerability.
**Prevention:** Catch exceptions and log the detailed raw exception string server-side. Save and emit only generic, sanitized messages (e.g., "An internal error occurred during HTML processing") to the database and client.
