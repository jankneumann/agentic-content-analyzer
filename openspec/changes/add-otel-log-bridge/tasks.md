# Implementation Tasks

## 1. Dependencies and Settings

- [x] 1.1 Add `opentelemetry-instrumentation-logging>=0.41b0` to `pyproject.toml` dependencies
- [x] 1.2 Add settings to `src/config/settings.py`:
  - `otel_logs_enabled: bool = True`
  - `otel_logs_export_level: str = "WARNING"`
  - `log_format: Literal["text", "json"] = "json"`
- [x] 1.3 Update `.env.example` with new settings and documentation comments

## 2. Extract Shared OTel Resource

- [x] 2.1 In `src/telemetry/otel_setup.py`, extract inline `Resource.create()` at lines 76-82
      into a `_create_resource() -> Resource` function
- [x] 2.2 Update `setup_otel_infrastructure()` to call `_create_resource()` for TracerProvider
- [x] 2.3 Verify existing trace tests still pass after refactor

## 3. Create OTel Log Bridge Module

- [x] 3.1 Create `src/telemetry/log_setup.py` with:
  - `setup_otel_log_bridge(resource) -> LoggerProvider | None`
  - `shutdown_otel_log_bridge() -> None`
  - Creates LoggerProvider with shared Resource
  - Creates OTLPLogExporter pointing to `{endpoint}/v1/logs`
  - Adds BatchLogRecordProcessor to LoggerProvider
  - Calls `LoggingInstrumentor().instrument(set_logging_format=False)` for trace context
  - Adds LoggingHandler to root logger with level from `otel_logs_export_level`
  - Returns None if `otel_enabled=False` or `otel_logs_enabled=False`
- [x] 3.2 Wire into `otel_setup.py`: call `setup_otel_log_bridge(resource)` after TracerProvider
- [x] 3.3 Wire into `src/telemetry/__init__.py`: call shutdown in `shutdown_telemetry()`

## 4. Console Formatters

- [x] 4.1 Add `JsonFormatter` to `src/utils/logging.py` — JSON lines with timestamp, level,
      logger, message, trace_id, span_id, extra attributes
- [x] 4.2 Add `TraceContextFormatter` — extends current text format, appends trace context
      when available
- [x] 4.3 Update `setup_logging()` to select formatter based on `settings.log_format`
- [x] 4.4 Ensure `get_logger(name)` API remains unchanged

## 5. Error Handler Cleanup

- [x] 5.1 Reviewed `_get_trace_id()` — kept manual `trace.get_current_span()` approach since
      it's called in exception handler context (not a log formatter). LoggingInstrumentor
      automatically enriches the `logger.error()` call within the handler instead.

## 6. Testing

- [x] 6.1 Create `tests/test_telemetry/test_log_setup.py`:
  - Bridge returns None when otel_enabled=False
  - Bridge returns None when otel_logs_enabled=False
  - LoggingHandler attached to root logger when enabled
  - LoggerProvider created with correct Resource
  - Shutdown cleans up LoggerProvider
- [x] 6.2 Create `tests/test_telemetry/test_log_correlation.py`:
  - Log records within active span have otelTraceID/otelSpanID set
  - Log records outside span have empty/zero trace context
  - Extra attributes preserved through bridge
  - JsonFormatter produces valid JSON output
  - TraceContextFormatter includes trace context
  - Export level filtering (WARNING exported, INFO not)
- [x] 6.3 Verify all existing tests pass with `pytest`

## 7. Documentation

- [x] 7.1 Update `docs/SETUP.md` with OTel log settings
- [x] 7.2 Update `CLAUDE.md` with gotchas:
  - `logging.basicConfig()` only works once — use `addHandler()` directly
  - Log bridge requires both `OTEL_ENABLED=true` AND `OTEL_LOGS_ENABLED=true`
  - Export level controls OTLP export, not console output
