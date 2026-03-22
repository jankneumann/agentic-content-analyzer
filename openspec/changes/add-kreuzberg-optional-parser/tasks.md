## 1. Dependency and Configuration

- [ ] 1.1 Add Kreuzberg as an optional dependency group and document installation/profile usage.
- [ ] 1.2 Add settings for `enable_kreuzberg`, parser preference controls, and any Kreuzberg-specific runtime options.
- [ ] 1.3 Ensure startup/import behavior remains graceful when Kreuzberg is not installed.

## 2. Parser Adapter

- [ ] 2.1 Implement `KreuzbergParser` conforming to `DocumentParser` (`parse`, `can_parse`, `name`).
- [ ] 2.2 Map Kreuzberg output into `DocumentContent` with markdown as canonical output and optional tables/links/metadata.
- [ ] 2.3 Add robust error handling and structured warnings for unsupported formats/timeouts.

## 3. Router Integration

- [ ] 3.1 Extend parser composition factory (upload/API and CLI entry points) to optionally register Kreuzberg.
- [ ] 3.2 Update routing policy to support Kreuzberg preference by format while preserving Docling OCR and MarkItDown default fallbacks.
- [ ] 3.3 Add deterministic precedence rules when multiple advanced parsers are enabled for the same format.

## 4. Shadow Evaluation and Observability

- [ ] 4.1 Add optional shadow mode to run Kreuzberg in parallel for selected formats without changing canonical persisted parser output.
- [ ] 4.2 Emit parse-quality and performance telemetry (success/failure, latency, content length, warning count, selected parser).
- [ ] 4.3 Add logging fields to support per-format promotion decisions and incident debugging.

## 5. Tests and Validation

- [ ] 5.1 Add unit tests for `KreuzbergParser` conversion and normalization behavior.
- [ ] 5.2 Add router tests for Kreuzberg-enabled/disabled behavior and fallback precedence.
- [ ] 5.3 Add integration tests covering upload/file ingestion with Kreuzberg installed and absent.
- [ ] 5.4 Add regression tests ensuring chunking strategy defaults remain stable for unknown parser identifiers.

## 6. Rollout

- [ ] 6.1 Ship with Kreuzberg disabled by default.
- [ ] 6.2 Enable shadow mode in staging and collect corpus-level metrics for a defined soak period.
- [ ] 6.3 Promote Kreuzberg for explicitly approved formats based on quality/performance thresholds.
