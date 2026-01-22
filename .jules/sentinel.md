## 2025-05-23 - [Information Leakage in Error Handling]
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` caught generic `Exception` and returned `str(e)` in the 500 response detail. This could expose stack traces, database connection strings, or file paths to the client.
**Learning:** Generic exception handlers that echo the error message to the user are a common source of information leakage. Developers often do this for debugging convenience but forget to remove it for production.
**Prevention:** Always catch generic exceptions and log them with `exc_info=True`, but return a generic "Internal Server Error" message to the client. Use specific exception handling (e.g., `ValueError`) for user-facing errors that are safe to expose.

## 2025-05-23 - [Path Traversal in Video Processing]
**Vulnerability:** The `KeyframeExtractor` in `src/ingestion/youtube_keyframes.py` used unvalidated `video_id` input to construct file paths for video downloads. This allowed path traversal (e.g., `../../evil`) if user input reached this method.
**Learning:** Even internal helper classes that process IDs should validate them, especially when performing filesystem operations. Trust boundaries are hard to define in evolving codebases.
**Prevention:** Always validate identifiers before using them in file paths. Use strict regex allowlists (e.g., `^[a-zA-Z0-9_-]+$`) for IDs.
