## 2025-05-27 - Information Leakage via Exception Details
**Vulnerability:** The `upload_document` endpoint in `src/api/upload_routes.py` was catching `ValueError` and returning `str(e)` to the client. This exposed potential secrets or internal paths if underlying libraries raised `ValueError` with sensitive details.
**Learning:** Using standard exceptions like `ValueError` for both expected validation errors (safe to expose) and unexpected internal errors (unsafe) makes it hard to handle them securely at the API layer.
**Prevention:** Define custom exceptions (e.g., `FileIngestionError`) for expected, safe-to-expose errors. Catch these specific exceptions in API routes. Allow unexpected exceptions to bubble up to a global error handler that returns generic 500 responses and logs details server-side.

## 2025-05-27 - Information Exposure in Global Error Handler
**Vulnerability:** The global error handlers `data_error_handler` and `asyncpg_data_error_handler` in `src/api/middleware/error_handler.py` were returning `exc.orig` and `exc` directly to the client in the 422 HTTP response detail field.
**Learning:** Returning raw database validation or asyncpg errors can expose sensitive internal details (e.g., query structure or internal systems state) to the end user.
**Prevention:** Global exception handlers should catch database and input errors but return sanitized generic strings like "Invalid parameter value" to the client.

## 2025-05-27 - Hardcoded API Key Exposure in Tests
**Vulnerability:** A hardcoded API key was found in a testing environment setup file or test case.
**Learning:** Including plain-text keys—even in mock setups or test cases—increases the risk of accidental commit or exposure when copied and modified.
**Prevention:** Use generic placeholder values (e.g., 'mock-secret-key' or 'app-secret-key') strictly for validation patterns without reflecting actual key formats.

## 2025-05-27 - Information Leakage via Exception Details in Pricing Routes
**Vulnerability:** The pricing API endpoints (`predict_monthly_costs`, `estimate_neon_cost`, `estimate_resend_cost`) in `src/api/pricing_routes.py` caught `ValueError` exceptions and returned their string representation (`str(e)`) directly to clients in a `400` response `detail` field.
**Learning:** Returning exception details from library calls or internally generated value errors can leak internal configuration structures or other unexpected details.
**Prevention:** Catch standard exceptions but map them to generic user-facing validation error messages like "Invalid parameters provided" rather than echoing the raw string representation directly in the API response.
