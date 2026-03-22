## Why

The document ingestion pipeline currently relies on MarkItDown for lightweight conversion and Docling for advanced PDF/OCR extraction. This provides strong baseline coverage, but it creates a two-backend architecture with limited optionality when parser quality varies by format or content shape.

Kreuzberg introduces an additional extraction backend that may improve format coverage and extraction quality for selected document classes. Adding Kreuzberg as an optional backend allows the system to compare parser quality per format, reduce single-vendor parser risk, and evolve routing decisions based on corpus-level evidence instead of static assumptions.

## What Changes

- Add an optional `KreuzbergParser` implementation under the existing `DocumentParser` abstraction.
- Add configuration flags to enable/disable Kreuzberg independently and control preferred formats.
- Extend parser router composition and routing policy to support Kreuzberg while preserving existing MarkItDown/Docling fallbacks.
- Normalize Kreuzberg extraction output to the existing `DocumentContent` contract (markdown primary, optional metadata/tables/links).
- Add a shadow-evaluation mode to compare Kreuzberg output against active parsers without changing canonical persisted content.
- Add parser metrics and logs to support format-level promotion decisions.

## Capabilities

### Modified Capabilities
- `document-parsing`: add optional Kreuzberg backend, routing preference controls, fallback behavior, and parser evaluation instrumentation.

## Impact

- **Backend parser layer**: new parser adapter + router decision path updates.
- **Configuration**: new feature flags and parser preference settings.
- **Observability**: additional parser metrics, structured logs, and comparison telemetry.
- **Testing**: new unit tests for parser adapter + router behavior and integration tests for fallback/shadow mode.
- **Operations**: optional dependency management and version pinning policy for Kreuzberg.

## Out of Scope

- Replacing MarkItDown or Docling globally in this change.
- Large-scale migration of historical content to re-parse old documents.
- Frontend UX changes beyond exposing parser availability metadata already returned by existing upload APIs.
