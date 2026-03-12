## 2025-05-27 - Information Leakage via Exception Details in Background Tasks DB Saving
**Vulnerability:** Several background task workers (`_generate_audio_digest_task`, `summarize_content`, `generate_script`, etc) caught `Exception as e` and saved `str(e)` directly into the database `error_message` fields. This exposed internal details, database connection strings, or paths to the frontend if users requested error details on failed tasks.
**Learning:** Background tasks updating database statuses on failure need the same level of generic sanitization as HTTP 500 error responses. Saving raw exceptions into the database makes them persistent and potentially visible to clients querying task status.
**Prevention:** Always log the full exception (`logger.error(..., exc_info=True)`) but save a static, generic error message (like "Task failed due to an internal error.") to database status fields.

## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.
