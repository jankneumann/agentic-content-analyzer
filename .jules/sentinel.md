## 2025-05-23 - [Information Leakage in Error Handling]
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` caught generic `Exception` and returned `str(e)` in the 500 response detail. This could expose stack traces, database connection strings, or file paths to the client.
**Learning:** Generic exception handlers that echo the error message to the user are a common source of information leakage. Developers often do this for debugging convenience but forget to remove it for production.
**Prevention:** Always catch generic exceptions and log them with `exc_info=True`, but return a generic "Internal Server Error" message to the client. Use specific exception handling (e.g., `ValueError`) for user-facing errors that are safe to expose.

## 2025-05-23 - [Path Traversal in Video Processing]
**Vulnerability:** The `KeyframeExtractor` in `src/ingestion/youtube_keyframes.py` used unvalidated `video_id` input to construct file paths for video downloads. This allowed path traversal (e.g., `../../evil`) if user input reached this method.
**Learning:** Even internal helper classes that process IDs should validate them, especially when performing filesystem operations. Trust boundaries are hard to define in evolving codebases.
**Prevention:** Always validate identifiers before using them in file paths. Use strict regex allowlists (e.g., `^[a-zA-Z0-9_-]+$`) for IDs.

## 2025-05-24 - [Inconsistent Input Validation]
**Vulnerability:** `YouTubeParser` relied on a weak length check (`len != 11`) for video IDs, while `KeyframeExtractor` used a robust regex check. This inconsistency allowed potentially malicious strings (e.g., shell injection payloads of length 11) to bypass validation in the parser, although downstream libraries likely mitigated the impact.
**Learning:** Security validation logic should be centralized and consistent across the application. When multiple components handle the same type of input (e.g., YouTube Video IDs), they should use a shared validation function.
**Prevention:** Refactor duplicated validation logic into shared utility functions (like `validate_video_id_format`) and ensure all consumers use them.

## 2025-05-24 - [Path Traversal in LocalFileStorage]
**Vulnerability:** `LocalFileStorage._resolve_path` in `src/services/file_storage.py` allowed directory traversal (e.g., `../`) because it concatenated user input with the base path without verifying the resolved location.
**Learning:** `pathlib.Path` joining operations do not automatically sanitize or sandbox paths. Explicit validation is necessary when handling file system paths derived from user input.
**Prevention:** Use `path.resolve().is_relative_to(base_path.resolve())` to enforce that file operations are confined within the intended directory.
