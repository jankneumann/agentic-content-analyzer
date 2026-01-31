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

## 2025-05-25 - [Path Traversal in LocalFileStorage]
**Vulnerability:** The `LocalFileStorage._resolve_path` method simply concatenated the base path with the user-provided relative path using `pathlib.Path` division operator (`/`). This allowed attackers to access files outside the storage directory using `../` segments (e.g., `images/../../etc/passwd`).
**Learning:** `pathlib.Path` concatenation does not automatically sandbox paths. If the right-hand operand contains `..`, the resulting path can resolve outside the left-hand operand's directory.
**Prevention:** Always use `.resolve()` on the final path and check `path.is_relative_to(base_path.resolve())` to ensure the file remains within the intended directory.

## 2025-05-26 - [Information Leakage in Chat API]
**Vulnerability:** The `generate_ai_response_streaming` and `apply_action` endpoints in `src/api/chat_routes.py` caught generic `Exception` and returned `str(e)` to the client, leaking potential sensitive details.
**Learning:** This vulnerability pattern (leaking `str(e)`) was previously identified in `upload_routes.py` but persisted in other endpoints. Security fixes must be applied systematically across the entire codebase, not just in the spot where they were first found.
**Prevention:** When identifying a vulnerability pattern, search the entire codebase for similar occurrences (e.g., `grep` for `str(e)` inside `except` blocks) to ensure complete remediation.

## 2025-05-27 - [Pervasive Error Leakage in Background Tasks]
**Vulnerability:** Background tasks for content ingestion (`content_routes.py`), summarization (`summary_routes.py`), and digest generation (`digest_routes.py`) were all catching generic `Exception` and saving `str(e)` to user-visible status fields (`message`, `review_notes`) or SSE streams. This confirmed the previous finding was part of a widespread pattern.
**Learning:** When moving logic to background tasks or SSE streams, developers often carry over the "return error string" pattern for status reporting, overlooking that these status updates are user-facing and can leak internal state (DB auth errors, API key issues).
**Prevention:** Treat task status messages and SSE error events as public API responses. Never include raw exception strings. Use generic error messages for the user and log the full traceback server-side.
