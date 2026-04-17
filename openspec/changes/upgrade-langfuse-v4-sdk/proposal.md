## Why

The current `LangfuseProvider` uses raw OpenTelemetry (`OTLPSpanExporter` → Langfuse's `/api/public/otel` endpoint), which sends generic spans that Langfuse cannot recognize as LLM generations. This means we miss Langfuse's core value: automatic cost tracking, token attribution, generation-typed spans, session grouping, and the `@observe()` decorator for pipeline-level tracing. The Braintrust provider already uses its native SDK for these exact reasons — Langfuse should follow the same pattern.

Langfuse Python SDK v4 (released March 2026) is built on OpenTelemetry internally, so it coexists with our existing OTel infrastructure instrumentation (`otel_setup.py`). Upgrading now aligns with our default provider choice (Langfuse) and unlocks features that raw OTel structurally cannot provide.

## What Changes

- **Replace raw OTel with native Langfuse SDK** in `src/telemetry/providers/langfuse.py`: use `langfuse.Langfuse()` / `langfuse.get_client()` instead of `OTLPSpanExporter` with manual Basic Auth
- **Add `langfuse>=4.3.0` as a core dependency** in `pyproject.toml` (not an optional extra — it's the default provider)
- **Add `opentelemetry-instrumentation-anthropic`** for automatic Claude call tracing via `AnthropicInstrumentor`
- **Add `@observe()` decorators** to all pipeline functions: `Summarizer`, `DigestCreator`, `ThemeAnalyzer`, `PodcastScriptGenerator`, and orchestrator entry points
- **Use `propagate_attributes()`** in pipeline runners for session/user context flow
- **Configure smart span filtering** via `should_export_span` to prevent noisy infrastructure spans from flooding Langfuse while keeping LLM-relevant spans
- **Update Settings** with new Langfuse v4 config fields: `langfuse_sample_rate`, `langfuse_debug`, `langfuse_environment`
- **Update the observability spec** to reflect native SDK behavior instead of raw OTel

## Capabilities

### New Capabilities

_None — this change enhances existing observability, it doesn't introduce a new capability._

### Modified Capabilities

- `observability`: LangfuseProvider requirements change from raw OTel export to native SDK with generation-typed spans, `@observe()` decorators, `AnthropicInstrumentor`, and `propagate_attributes()` context flow

## Impact

- **`src/telemetry/providers/langfuse.py`**: Full rewrite — raw OTel → native Langfuse SDK
- **`src/telemetry/providers/factory.py`**: Constructor args may change (SDK handles auth via env vars or constructor)
- **`src/telemetry/providers/base.py`**: Protocol unchanged — `trace_llm_call()`, `start_span()`, `flush()`, `shutdown()` signatures stay the same
- **`src/telemetry/__init__.py`**: No changes expected (lazy singleton pattern works with new provider)
- **`src/services/llm_router.py`**: `_trace_llm_call()` continues working via Protocol; `AnthropicInstrumentor` may make explicit tracing redundant for Anthropic calls but we keep it for provider-agnosticism
- **`src/processors/summarizer.py`**: Add `@observe()` decorator (complements existing `_summarization_span` helper)
- **`src/processors/digest_creator.py`**: Add `@observe()` decorator
- **`src/processors/theme_analyzer.py`**: Add `@observe()` decorator
- **`src/processors/podcast_script_generator.py`**: Add `@observe()` decorator
- **`src/ingestion/orchestrator.py`**: Add `@observe()` to orchestrator entry points
- **`src/pipeline/runner.py`**: Add `propagate_attributes()` for session context
- **`pyproject.toml`**: Add `langfuse>=4.3.0` to core dependencies, add `opentelemetry-instrumentation-anthropic`
- **`src/config/settings.py`**: New settings fields for Langfuse v4
- **`profiles/`**: Update `local-langfuse` profile for any new env vars
- **`openspec/specs/observability/spec.md`**: Update Langfuse requirements section
- **No breaking changes** to the `ObservabilityProvider` Protocol — all other providers (noop, braintrust, opik, otel) are unaffected
