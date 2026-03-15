## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2024-03-15 - [Medium] Fix Information Exposure in DataError exceptions
**Vulnerability:** SQLAlchemy `DataError` and `AsyncpgDataError` exceptions were leaking raw database error messages (`exc.orig` and `exc`) in the HTTP 422 Unprocessable Entity response `detail` field.
**Learning:** Global error handlers that convert database-level validation failures into HTTP responses must be careful not to blindly echo the underlying exception strings, as they can contain sensitive schema details, column names, or the sensitive parameter values that caused the error.
**Prevention:** Always map database-level exceptions to generic, safe error messages (like "Invalid parameter value") for the HTTP response, while logging the full exception internally for debugging.
