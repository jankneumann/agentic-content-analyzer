## Context

The `LangfuseProvider` currently uses raw OpenTelemetry (`OTLPSpanExporter` with Basic Auth headers) to send spans to Langfuse's OTLP endpoint. This was a pragmatic choice — Langfuse accepts OTel data — but it means Langfuse sees generic spans, not generation-typed observations. The Braintrust provider already uses its native SDK (`import braintrust`) for richer tracing; the Langfuse provider should follow the same pattern.

Langfuse Python SDK v4 (released March 2026, current: v4.3.1) is built on OpenTelemetry internally. It emits OTel spans but enriches them with Langfuse-specific attributes that the Langfuse backend recognizes. This means it coexists with our existing OTel infrastructure auto-instrumentation (`src/telemetry/otel_setup.py`) without conflict.

**Current call flow:**
```
LLMRouter._trace_llm_call()
  → get_provider() → LangfuseProvider.trace_llm_call()
    → OTel span with gen_ai.* attributes
      → OTLPSpanExporter → Langfuse /api/public/otel
        → Langfuse sees: generic span (not a "generation")
```

**Target call flow:**
```
LLMRouter._trace_llm_call()
  → get_provider() → LangfuseProvider.trace_llm_call()
    → langfuse.start_as_current_observation(as_type="generation")
      → Langfuse sees: generation with model, tokens, cost

@observe()-decorated pipeline functions
  → automatic span creation with inputs/outputs
    → nested trace tree in Langfuse UI

AnthropicInstrumentor (optional)
  → auto-wraps anthropic.Anthropic client calls
    → generation spans with full request/response capture
```

## Goals / Non-Goals

**Goals:**
- Replace raw OTel export with native Langfuse SDK for generation-typed spans, cost tracking, and session grouping
- Add `@observe()` decorators to key pipeline functions for end-to-end trace visibility
- Maintain `ObservabilityProvider` Protocol contract — other providers unaffected
- Add `AnthropicInstrumentor` for automatic Claude call tracing
- Keep the `LLMRouter._trace_llm_call()` path working (explicit tracing as fallback/complement)

**Non-Goals:**
- Abstracting `@observe()` behind a provider-agnostic decorator — decorators are inherently SDK-specific, and trying to abstract them adds complexity without value
- Adding Langfuse prompt management or evaluation features — those are separate concerns
- Modifying other providers (noop, opik, braintrust, otel)
- Changing the `ObservabilityProvider` Protocol interface
- Wrapping the OpenAI client (we don't use OpenAI directly for core pipeline work)

## Decisions

### 1. Langfuse SDK as core dependency, not optional extra

**Decision:** Add `langfuse>=4.3.0` to core `dependencies` in `pyproject.toml`.

**Alternatives considered:**
- Optional extra like braintrust (`pip install .[langfuse]`): Rejected because Langfuse is the default provider. Making it optional means the default configuration fails without extra install steps.
- Keep raw OTel: Rejected because it structurally cannot provide generation-typed spans, cost tracking, or `@observe()`.

**Rationale:** Braintrust is an optional extra because it's an override option. Langfuse is the default — it should work out of the box.

### 2. Use `AnthropicInstrumentor` for automatic Claude tracing

**Decision:** Install `opentelemetry-instrumentation-anthropic` and call `AnthropicInstrumentor().instrument()` in `LangfuseProvider.setup()`.

**Alternatives considered:**
- Manual `langfuse.start_as_current_observation(as_type="generation")` around each LLM call: More control but duplicates what the instrumentor does automatically.
- `langfuse.openai.OpenAI` wrapper via Anthropic's OpenAI-compatible endpoints: Rejected — adds indirection, and our codebase uses the native Anthropic SDK directly.

**Rationale:** The instrumentor auto-captures all `anthropic.Anthropic` calls with zero code changes in `LLMRouter`. Combined with `@observe()` on pipeline functions, this gives full trace trees. The explicit `trace_llm_call()` path remains as defense-in-depth for non-Anthropic providers (Gemini, OpenAI).

### 3. Smart span filtering to prevent noise

**Decision:** Configure `should_export_span` to only export Langfuse SDK spans, `gen_ai.*` spans, and `AnthropicInstrumentor` spans.

**Alternatives considered:**
- Export all spans (`should_export_span=lambda span: True`): Rejected — our OTel infrastructure instrumentation (FastAPI, SQLAlchemy, httpx) would flood Langfuse with HTTP/DB spans that belong in the generic OTel backend, not the LLM observability view.
- Default v4 filter only: Acceptable, but we may want to extend it for our custom scopes later.

**Rationale:** The v4 default filter already handles this well (exports Langfuse SDK + `gen_ai.*` + known LLM instrumentors). Start with the default and extend via `is_default_export_span()` composition if needed.

### 4. Keep `trace_llm_call()` alongside `AnthropicInstrumentor`

**Decision:** `LangfuseProvider.trace_llm_call()` uses `start_as_current_observation(as_type="generation")` for explicit generation tracing. `AnthropicInstrumentor` auto-captures at the SDK level. Both coexist.

**Alternatives considered:**
- Remove `trace_llm_call()` entirely and rely on instrumentor: Rejected — `trace_llm_call()` is the Protocol contract, and it's used for all providers including non-Anthropic models (Gemini via OpenAI, etc.) where `AnthropicInstrumentor` won't fire.
- Disable instrumentor and only use `trace_llm_call()`: Loses the automatic input/output/token capture that the instrumentor provides.

**Rationale:** Potential for duplicate spans for Anthropic calls (one from instrumentor, one from `trace_llm_call`). Mitigation: add a check in `trace_llm_call()` — if the current span is already an Anthropic instrumentor span, skip creating a new generation. Or accept the minor duplication since Langfuse deduplicates by trace context.

### 5. `@observe()` directly on pipeline functions, not abstracted

**Decision:** Import `langfuse.observe` and apply it directly. When Langfuse is not the active provider, `@observe()` is a no-op (Langfuse SDK gracefully degrades when not configured).

**Alternatives considered:**
- Provider-agnostic `@trace_function()` decorator: Rejected — each SDK's decorator has different parameters and context propagation. Abstracting them is leaky and fragile.
- Conditional application (`if provider.name == "langfuse"`): Unnecessary complexity — `@observe()` is already a no-op without Langfuse configuration.

**Rationale:** `@observe()` does nothing when Langfuse env vars aren't set. So adding it to pipeline functions has zero overhead for non-Langfuse providers. This is the simplest approach.

### 6. Isolated TracerProvider to avoid conflicts with otel_setup.py

**Decision:** Use `Langfuse()` constructor which creates its own TracerProvider, not overwriting the global one.

**Alternatives considered:**
- Share the global TracerProvider: Rejected — `otel_setup.py` sets up the global provider for infrastructure instrumentation (FastAPI, SQLAlchemy, httpx). Langfuse SDK's span filter would interfere with those exports.

**Rationale:** The current raw OTel provider already uses an isolated TracerProvider (line 141 of current `langfuse.py`). The SDK maintains this isolation by default.

## Risks / Trade-offs

- **[Duplicate Anthropic spans]** → `AnthropicInstrumentor` and `trace_llm_call()` may both create generation spans for Claude calls. Mitigation: test and verify — if duplicated, add a guard in `trace_llm_call()` to check for active instrumentor span.
- **[Pydantic v2 requirement]** → Langfuse SDK v4 requires Pydantic v2. We already use Pydantic v2 (`pydantic-settings`), so no conflict expected. Verify in CI.
- **[Self-hosted v2 API endpoints]** → SDK v4 defaults to v2 API endpoints that may not be available on older self-hosted Langfuse. Mitigation: our docker-compose uses a recent Langfuse image; document minimum version in SETUP.md.
- **[`metadata` validation stricter in v4]** → Metadata values must be `dict[str, str]` with 200-char limit. Our existing `trace_llm_call()` passes arbitrary metadata. Mitigation: coerce values to strings and truncate in the provider.
- **[SDK dependency size]** → Adding `langfuse` as a core dep increases install size. Trade-off is acceptable since it's the default provider and replaces manual OTel wiring.

## Migration Plan

1. Add `langfuse>=4.3.0` and `opentelemetry-instrumentation-anthropic` to `pyproject.toml`
2. Rewrite `LangfuseProvider` to use native SDK
3. Update factory constructor args if needed
4. Add `@observe()` to pipeline functions
5. Update settings with new Langfuse v4 fields
6. Update spec delta
7. Test with local Langfuse stack (`make langfuse-up`)
8. Verify in Langfuse UI: generations visible, cost tracked, trace trees nested

**Rollback:** Set `OBSERVABILITY_PROVIDER=otel` or `noop` — the old raw OTel provider (`OTelProvider`) still works for generic OTLP export. No data loss since Langfuse retains historical traces.
