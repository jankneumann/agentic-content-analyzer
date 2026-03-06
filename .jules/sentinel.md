## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.
## 2023-11-20 - [Fix database error detail leakage in error handler]
**Vulnerability:** The global error handler was exposing detailed database error strings (`exc.orig` and `exc`) in the HTTP 422 Unprocessable Entity responses for `DataError` and `AsyncpgDataError`. This could potentially leak database schema internals, data values, or backend configurations to an attacker.
**Learning:** Returning raw exception details in API responses is an anti-pattern. While logging the full exception is crucial for debugging, the user-facing response must be sanitized.
**Prevention:** Always replace database exception specifics with generic error messages (e.g., "Invalid parameter value") in error handlers, while ensuring the original exception is captured securely in server logs.
