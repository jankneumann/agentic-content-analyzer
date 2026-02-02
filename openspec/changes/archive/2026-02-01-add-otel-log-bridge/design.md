# Design: OTel Log Bridge

## Context

The project already has traces (`TracerProvider` + `BatchSpanProcessor` + `OTLPSpanExporter` in
`src/telemetry/otel_setup.py`) and metrics (`OTel Meter` in `src/telemetry/metrics.py`). Logs
are the third and final OTel signal. The Python OTel SDK provides a Log Bridge API specifically
designed for this use case: bridging existing stdlib `logging` to the OTel data model without
replacing the logging API.

83 source files use `from src.utils.logging import get_logger`, which returns a standard
`logging.Logger`. One file (`src/api/middleware/error_handler.py`) uses `extra={}` for structured
data. The remaining files use plain string formatting.

## Goals

1. Bridge stdlib `logging` to OTel Log Data Model with zero call-site changes
2. Automatic trace-log correlation (TraceId/SpanId injected into every log record)
3. OTLP export of logs to the same backend as traces
4. Shared OTel Resource (service.name, environment) across traces, metrics, and logs
5. Structured JSON console output by default; human-readable text as opt-in

## Non-Goals

1. Rewriting existing log call sites to use structured attributes (future enhancement)
2. Replacing Python stdlib logging with a different logging library
3. Log-based alerting or log aggregation pipeline configuration
4. Console log exporter for OTel (we use the stdlib StreamHandler for console)

## Decisions

### Decision 1: Separate `log_setup.py` Module

Create `src/telemetry/log_setup.py` for all log bridge configuration, called from
`setup_otel_infrastructure()` in `otel_setup.py`.

Follows the existing pattern where `otel_setup.py` handles infrastructure setup and
`metrics.py` is a separate module.

### Decision 2: Two-Phase Initialization

`setup_logging()` runs first (configures root logger with StreamHandler), then
`setup_otel_log_bridge()` runs during `setup_telemetry()` (adds OTel LoggingHandler as a
second handler on the root logger).

Key insight: `logging.basicConfig()` only works on the first call. Since `setup_logging()`
calls it first, the OTel bridge must use `logging.getLogger().addHandler()` directly, not
`basicConfig()`.

### Decision 3: LoggingInstrumentor for Trace Context Injection

Use `opentelemetry.instrumentation.logging.LoggingInstrumentor` to automatically inject
`otelTraceID`, `otelSpanID`, `otelServiceName`, and `otelTraceSampled` attributes into every
log record.

Set `set_logging_format=False` — we manage our own format. The instrumentor should only inject
the attributes; we control how they appear in console output.

### Decision 4: JSON Default Console Format

`LOG_FORMAT=json` is the default. Every log record is a JSON object with timestamp, level,
logger name, message, trace_id, span_id, and any `extra={}` attributes. Call sites do NOT
need changes; the `JsonFormatter` wraps the existing `record.getMessage()` string.

Developers who prefer readable output during local debugging set `LOG_FORMAT=text`.

### Decision 5: OTel LoggingHandler Configuration

Add `opentelemetry.sdk._logs.LoggingHandler` to the root logger with:
- `level` from `otel_logs_export_level` setting (default: WARNING)
- `logger_provider` from shared LoggerProvider

Pipeline:
```
LoggerProvider(resource=shared_resource)
  └── BatchLogRecordProcessor
        └── OTLPLogExporter(endpoint=.../v1/logs, headers=same)
```

### Decision 6: Resource Sharing

Extract `Resource.create()` from `setup_otel_infrastructure()` into a shared
`_create_resource()` function that both TracerProvider and LoggerProvider use.

### Decision 7: Settings

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `otel_logs_enabled` | `bool` | `True` | Enable log bridge (gated by `otel_enabled`) |
| `otel_logs_export_level` | `str` | `"WARNING"` | Min level for OTLP export |
| `log_format` | `Literal["text","json"]` | `"json"` | Console format |

## Architecture

```
Application Code (83+ files)
  │
  └── logger.info("Processing item", extra={"source": "gmail"})
        │
        ├── [Handler 1] StreamHandler → stdout
        │     └── JsonFormatter (default) or TraceContextFormatter (text mode)
        │
        └── [Handler 2] OTel LoggingHandler → LoggerProvider
              │
              ├── LoggingInstrumentor auto-injects trace context
              │
              └── BatchLogRecordProcessor
                    └── OTLPLogExporter (HTTP) → Same OTLP endpoint as traces
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Log volume overwhelms OTLP backend | `otel_logs_export_level` defaults to WARNING |
| Performance overhead of dual handlers | BatchLogRecordProcessor is async; minimal impact |
| `logging.basicConfig()` already called | Use `addHandler()` directly |
| JSON format breaks existing log parsing | JSON is default but text available via `LOG_FORMAT=text` |
| OTel log SDK uses `_logs` (underscore) | Stable in practice; the API is widely used in production |
