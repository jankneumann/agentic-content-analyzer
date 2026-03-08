## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2025-05-27 - Information Leakage via Global Exception Handler
**Vulnerability:** The global error handler in `src/api/middleware/error_handler.py` was exposing raw database exception details (`DataError` and `AsyncpgDataError`) to the client via the HTTP 422 Unprocessable Entity response.
**Learning:** Database exception messages often contain sensitive internal state such as query structures, table names, or specific row data that failed validation. Returning these dynamically directly to the client leaks database internals.
**Prevention:** Always serialize a static, generic string (e.g. "Invalid parameter value") in user-facing error responses for database/validation errors. Log the detailed exception server-side for internal debugging.
