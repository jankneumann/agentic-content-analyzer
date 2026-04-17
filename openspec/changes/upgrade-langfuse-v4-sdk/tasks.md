## 1. Dependencies

_No dependencies on other groups. Groups 2 and 5 can start in parallel after this._

- [ ] 1.1 Add `langfuse>=4.3.0` to core `dependencies` in `pyproject.toml`
- [ ] 1.2 Add `opentelemetry-instrumentation-anthropic` to core `dependencies` in `pyproject.toml`
- [ ] 1.3 Run `uv sync` and verify both packages install cleanly alongside existing OTel deps

## 2. Settings & Configuration

_Depends on: group 1. Blocked by: nothing else._

- [ ] 2.1 Add settings fields to `src/config/settings.py`: `langfuse_sample_rate: float = 1.0`, `langfuse_debug: bool = False`, `langfuse_environment: str | None = None`. Add a `field_validator` for `langfuse_sample_rate` that clamps to 0.0-1.0 and logs a warning if the input value was out of range.
- [ ] 2.2 Wire new settings into `profiles/local-langfuse.yaml` with appropriate defaults
- [ ] 2.3 Add `LANGFUSE_SAMPLE_RATE`, `LANGFUSE_DEBUG`, `LANGFUSE_ENVIRONMENT` to `.secrets.yaml` interpolation in `profiles/base.yaml` if needed

## 3. Rewrite LangfuseProvider

_Depends on: group 2 (needs new settings fields). Files: `src/telemetry/providers/langfuse.py` only._

- [ ] 3.1 Rewrite `src/telemetry/providers/langfuse.py` to use `langfuse.Langfuse()` constructor instead of `OTLPSpanExporter` — pass `public_key`, `secret_key`, `base_url`, `sample_rate`, `debug`, `environment` from settings
- [ ] 3.2 Implement `trace_llm_call()` using `langfuse.start_as_current_observation(as_type="generation", model=..., usage={...})` for generation-typed observations. Sanitize metadata to `dict[str, str]` with 200-char value truncation before passing to Langfuse (v4 requirement).
- [ ] 3.3 Implement `start_span()` using `langfuse.start_as_current_observation(as_type="span", name=...)` for pipeline spans
- [ ] 3.4 Implement `flush()` via `langfuse.flush()` and `shutdown()` via `langfuse.flush()` + cleanup
- [ ] 3.5 Add `AnthropicInstrumentor().instrument()` call in `setup()` with graceful fallback if `opentelemetry-instrumentation-anthropic` is not installed
- [ ] 3.6 Configure smart span filtering: use default v4 filter (Langfuse SDK + `gen_ai.*` + known LLM instrumentors) — ensure infrastructure spans from `otel_setup.py` are NOT exported to Langfuse
- [ ] 3.7 Add warning logs for missing/partial API keys (preserve existing behavior)
- [ ] 3.8 Ensure isolated TracerProvider — Langfuse SDK must not overwrite the global OTel provider used by `otel_setup.py`
- [ ] 3.9 Handle potential duplicate Anthropic spans: if `AnthropicInstrumentor` is active and the current observation is already a generation from the instrumentor, `trace_llm_call()` should update the existing observation rather than creating a duplicate

## 4. Update Factory

_Depends on: groups 2 and 3. Files: `src/telemetry/providers/factory.py` only._

- [ ] 4.1 Update `src/telemetry/providers/factory.py` `langfuse` case to pass new settings fields (`sample_rate`, `debug`, `environment`) to `LangfuseProvider` constructor
- [ ] 4.2 Verify the `ObservabilityProvider` Protocol still type-checks with the rewritten provider (mypy)

## 5. Add @observe() Decorators to Pipeline Functions

_Independent of groups 3-4 (decorators work regardless of provider). Can be parallelized with group 3. Files: `src/processors/`, `src/ingestion/orchestrator.py`, `src/pipeline/runner.py`._

- [ ] 5.1 Add `@observe()` to `DigestCreator.create_digest()` in `src/processors/digest_creator.py`
- [ ] 5.2 Add `@observe()` to `ThemeAnalyzer.analyze()` in `src/processors/theme_analyzer.py`
- [ ] 5.3 Add `@observe()` to orchestrator entry points in `src/ingestion/orchestrator.py` (`ingest_gmail`, `ingest_rss`, `ingest_youtube_playlist`, `ingest_youtube_rss`, `ingest_podcast`, `ingest_substack`)
- [ ] 5.4 Add `@observe()` to `_run_ingestion()` and other pipeline stages in `src/pipeline/runner.py`
- [ ] 5.5 Add `propagate_attributes()` in the pipeline runner's top-level entry point to flow `session_id` and `tags` to all child observations

## 6. Tests

_Depends on: groups 3, 4, and 5. Files: `tests/telemetry/`._

- [ ] 6.1 Unit test: `LangfuseProvider` initializes with `langfuse.Langfuse()` and creates generation observations via `trace_llm_call()` — mock the Langfuse client
- [ ] 6.2 Unit test: `LangfuseProvider.start_span()` creates span observations — mock the Langfuse client
- [ ] 6.3 Unit test: `LangfuseProvider` handles missing `langfuse` package gracefully (ImportError → log error, methods become no-ops)
- [ ] 6.4 Unit test: `LangfuseProvider` handles missing/partial API keys with appropriate warnings
- [ ] 6.5 Unit test: Factory creates `LangfuseProvider` with new settings fields
- [ ] 6.6 Unit test: `@observe()` decorator on pipeline functions — verify decorated function return values and side effects are unchanged when Langfuse is not configured, and exceptions propagate unmodified
- [ ] 6.7 Unit test: metadata sanitization — verify arbitrary dict values are coerced to `dict[str, str]` with 200-char truncation
- [ ] 6.8 Verify existing provider tests (noop, braintrust, opik, otel) still pass — no regressions

## 7. Documentation & Spec Update

_Depends on: groups 2-5. Files: `docs/SETUP.md`, profiles._

- [ ] 7.1 Update `docs/SETUP.md` observability section to document Langfuse SDK v4 configuration
- [ ] 7.2 Update `profiles/local-langfuse.yaml` with any new env vars
- [ ] 7.3 Verify `make langfuse-up` still works with the new SDK — ensure docker-compose Langfuse image supports v2 API endpoints required by SDK v4
