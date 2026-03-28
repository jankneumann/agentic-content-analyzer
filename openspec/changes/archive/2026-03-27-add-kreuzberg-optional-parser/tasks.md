## 1. Dependency and Configuration

- [x] 1.1 Add Kreuzberg as an optional dependency group and document installation/profile usage.
- [x] 1.2 Add settings for `enable_kreuzberg`, parser preference controls, and any Kreuzberg-specific runtime options.
- [x] 1.3 Ensure startup/import behavior remains graceful when Kreuzberg is not installed.

## 2. Parser Adapter

- [x] 2.1 Implement `KreuzbergParser` conforming to `DocumentParser` (`parse`, `can_parse`, `name`).
- [x] 2.2 Map Kreuzberg output into `DocumentContent` with markdown as canonical output and optional tables/links/metadata.
- [x] 2.3 Add robust error handling and structured warnings for unsupported formats/timeouts.

## 3. Router Integration

- [x] 3.1 Extend parser composition factory (upload/API and CLI entry points) to optionally register Kreuzberg.
- [x] 3.2 Update routing policy to support Kreuzberg preference by format while preserving Docling OCR and MarkItDown default fallbacks.
- [x] 3.3 Add deterministic precedence rules when multiple advanced parsers are enabled for the same format.

## 4. Shadow Evaluation and Observability

- [x] 4.1 Add optional shadow mode to run Kreuzberg in parallel for selected formats without changing canonical persisted parser output.
- [x] 4.2 Emit parse-quality and performance telemetry (success/failure, latency, content length, warning count, selected parser).
- [x] 4.3 Add logging fields to support per-format promotion decisions and incident debugging.

## 5. Tests and Validation

- [x] 5.1 Add unit tests for `KreuzbergParser` conversion and normalization behavior.
- [x] 5.2 Add router tests for Kreuzberg-enabled/disabled behavior and fallback precedence.
- [x] 5.3 Add integration tests covering upload/file ingestion with Kreuzberg installed and absent.
- [x] 5.4 Add regression tests ensuring chunking strategy defaults remain stable for unknown parser identifiers.

## 6. Rollout

- [x] 6.1 Ship with Kreuzberg disabled by default.
- [ ] 6.2 Enable shadow mode in staging and collect corpus-level metrics for a defined soak period.
- [ ] 6.3 Promote Kreuzberg for explicitly approved formats based on quality/performance thresholds.
