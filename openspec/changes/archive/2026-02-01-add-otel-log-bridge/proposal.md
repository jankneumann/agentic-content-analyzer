# Change: Add OpenTelemetry Log Bridge for Trace-Log Correlation

## Why

The application has 83+ files using `get_logger()` from `src/utils/logging.py`, but logs are
plain text to stdout with no structure, no trace correlation, and no export capability. Traces
(pillar 1) and metrics (pillar 2) are already configured via `src/telemetry/otel_setup.py` and
`src/telemetry/metrics.py`. Logs are the missing third pillar.

Without the log bridge:
- Logs cannot be correlated with traces (no TraceId/SpanId in log records)
- Logs cannot be exported to the same observability backend as traces
- No structured logging means log aggregation tools cannot index or query log attributes
- The error handler (`src/api/middleware/error_handler.py:15-25`) manually extracts trace_id
  instead of getting it automatically from the log record

By adding the OTel log bridge:
1. **Automatic trace-log correlation**: Every log emitted within a traced request automatically
   includes TraceId and SpanId — no code changes at call sites
2. **Unified export**: Logs flow to the same OTLP endpoint as traces (Opik, Jaeger, etc.)
3. **Structured JSON output**: All logs output as queryable JSON objects by default
4. **Three pillars complete**: Traces + Metrics + Logs share the same OTel Resource identity
5. **Zero disruption**: Existing 83+ `get_logger()` call sites continue working unchanged

## What Changes

- **NEW** `src/telemetry/log_setup.py` — OTel log bridge (LoggerProvider, LoggingHandler,
  BatchLogRecordProcessor, OTLPLogExporter)
- **NEW** `tests/test_telemetry/test_log_setup.py` — Bridge enable/disable tests
- **NEW** `tests/test_telemetry/test_log_correlation.py` — Trace-log correlation tests
- **MODIFIED** `src/utils/logging.py` — Add JsonFormatter (default), TraceContextFormatter;
  select based on `LOG_FORMAT` setting
- **MODIFIED** `src/telemetry/otel_setup.py` — Extract shared Resource helper; call log bridge
  setup after TracerProvider
- **MODIFIED** `src/telemetry/__init__.py` — Wire log bridge into lifecycle
- **MODIFIED** `src/config/settings.py` — Add `otel_logs_enabled`, `otel_logs_export_level`,
  `log_format` settings
- **MODIFIED** `src/api/middleware/error_handler.py` — Simplify trace_id extraction
- **MODIFIED** `pyproject.toml` — Add `opentelemetry-instrumentation-logging` dependency

### Not Changed (by design)
- No modification to any of the 83+ files that call `get_logger()` — the bridge enriches
  existing log records automatically
- No modification to LLM provider implementations — they already use the project logger
- No modification to the ObservabilityProvider protocol — logs are an infrastructure-level
  concern, not an LLM observability concern

## Impact

- Affected specs: `observability` (add log bridge and structured logging requirements)
- Affected code:
  - `src/utils/logging.py` (setup_logging, formatters)
  - `src/telemetry/otel_setup.py` (Resource sharing, log bridge call)
  - `src/telemetry/__init__.py` (lifecycle)
  - `src/config/settings.py` (new settings)
  - `src/api/middleware/error_handler.py` (simplified trace_id)
  - `pyproject.toml` (new dependency)
- New files: `src/telemetry/log_setup.py`, 2 test files
- Dependencies: `opentelemetry-instrumentation-logging` (new)

## Related Proposals

- `add-observability` — Parent proposal; this extends it with the third OTel signal
