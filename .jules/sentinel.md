## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2025-05-28 - Information Leakage via Database Exceptions
**Vulnerability:** The `data_error_handler` and `asyncpg_data_error_handler` in `src/api/middleware/error_handler.py` leaked internal database details by including `{exc.orig}` and `{exc}` in the 422 Unprocessable Entity JSON response.
**Learning:** Database validation exceptions (e.g., `sqlalchemy.exc.DataError`, `asyncpg.exceptions.DataError`) often contain the raw SQL statements, parameter values, or underlying schema constraints. Exposing these to clients gives attackers insight into the database structure.
**Prevention:** Always sanitize database error details in HTTP responses. Global exception handlers should log the full exception internally but return generic messages (e.g., "Invalid parameter format or value") to the client.
