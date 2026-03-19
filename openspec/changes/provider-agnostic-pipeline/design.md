## Context

Pipeline steps (summarization via `ClaudeAgent`, digest revision via `DigestReviser`) bypass `LLMRouter` and hardcode Anthropic SDK client creation. Setting `MODEL_SUMMARIZATION=gemini-2.5-flash-lite` caused all 1,568 content items to fail because `ClaudeAgent` filters providers to only `ANTHROPIC`, `AWS_BEDROCK`, `GOOGLE_VERTEX` — rejecting `GOOGLE_AI`.

Meanwhile, `LLMRouter` (`src/services/llm_router.py`) already supports all 6 providers and is correctly used by `ThemeAnalyzer`. The fix is to route `ClaudeAgent` and `DigestReviser` through `LLMRouter` instead of duplicating provider logic.

**Key constraint**: `SummarizationAgent.summarize_content()` is a synchronous abstract method (called from sync `ContentSummarizer` and `asyncio.to_thread()` in the queue worker), but `LLMRouter.generate()` is async-only.

## Goals / Non-Goals

**Goals:**
- Any configured provider (Anthropic, Google AI, OpenAI, Bedrock, Vertex, Azure) works at any pipeline step
- `MODEL_SUMMARIZATION=gemini-2.5-flash-lite` works without code changes
- Provider failover, cost tracking, and telemetry continue to work
- No breaking changes to public APIs or CLI

**Non-Goals:**
- Converting `SummarizationAgent` from sync to async (would require changing `ContentSummarizer`, queue worker, and all callers)
- Adding new providers beyond what `LLMRouter` already supports
- Changing prompt templates or summarization logic

## Decisions

### 1. Add `LLMRouter.generate_sync()` — sync entry point

**Choice**: Extract sync core helpers from existing async methods, add a `generate_sync()` public method.

**Rationale**: The Anthropic SDK (`client.messages.create()`) and google-genai SDK (`client.models.generate_content()`) are synchronous calls wrapped in `async def` methods. Extracting `_generate_anthropic_sync()` and `_generate_gemini_sync()` avoids `asyncio.run()` nesting issues (which fail if an event loop is already running, as in the queue worker).

For OpenAI, the SDK provides both `OpenAI` (sync) and `AsyncOpenAI` (async). Add `_get_openai_sync_client()` → `OpenAI`/`AzureOpenAI` and `_generate_openai_sync()`.

**Alternative considered**: Using `asyncio.run()` wrapper — rejected because the queue worker already runs an event loop, and nested `asyncio.run()` raises `RuntimeError`.

**Alternative considered**: Using `nest_asyncio` — rejected because it patches the global event loop and can mask concurrency bugs.

**Implementation**:
- `_generate_anthropic_sync()` — same body as `_generate_anthropic()` (already sync internally)
- `_generate_gemini_sync()` — same body as `_generate_gemini()` (already sync internally)
- `_generate_openai_sync()` — uses sync `OpenAI`/`AzureOpenAI` client
- `generate_sync()` — routes to the appropriate sync helper based on resolved provider, includes telemetry tracing

### 2. Refactor `ClaudeAgent` → `LLMSummarizationAgent`

**Choice**: Replace direct Anthropic SDK usage with `LLMRouter.generate_sync()`. Keep `ClaudeAgent` as backward-compat alias.

**Rationale**: `ClaudeAgent` currently duplicates the provider resolution, client creation, and failover logic that `LLMRouter` already handles. By delegating to `LLMRouter`, the agent automatically supports all providers.

**Implementation**:
- Constructor: create `LLMRouter(model_config)` internally
- Extract shared `_generate_summary(system_prompt, user_prompt, content) -> AgentResponse` helper (deduplicates ~90% identical code between `summarize_content()` and `summarize_content_with_feedback()`)
- Remove `_get_client()` — no longer needed
- Remove the `compatible_providers` filter — `LLMRouter` handles provider resolution
- Keep `_extract_json_from_response()`, `_create_content_prompt()`, `_create_content_feedback_prompt()` — domain logic unchanged
- Update `framework_name` to derive from model family (not hardcoded "claude")

**Files**:
- `src/agents/claude/summarizer.py` — refactor class
- `src/agents/claude/__init__.py` — export `LLMSummarizationAgent`, keep `ClaudeAgent` alias

### 3. Refactor `DigestReviser` to use `LLMRouter`

**Choice**: Use `LLMRouter.generate_with_tools()` (async) to replace manual Anthropic tool-use loop.

**Rationale**: `DigestReviser.revise_section()` is already async, so it can call `LLMRouter.generate_with_tools()` directly. The tool definitions (`fetch_content`, `search_content`) map cleanly to `ToolDefinition` objects. The existing `_handle_tool_call()` method becomes the `tool_executor` callback.

**Implementation**:
- Constructor: create `LLMRouter(model_config)` internally
- Convert `_get_tool_definitions()` from Anthropic format → `ToolDefinition` objects
- Create async `_execute_tool(name, args) -> str` wrapper around `_handle_tool_call()`
- `revise_section()`: call `self.router.generate_with_tools()` instead of manual loop
- Track `provider_used`, `input_tokens`, `output_tokens` from `LLMResponse`
- Remove `from anthropic import Anthropic` import

**Files**:
- `src/processors/digest_reviser.py` — refactor to use LLMRouter

### 4. Reset failed content items

**Choice**: SQL UPDATE to reset 1,568 items from `failed` to `pending`.

**Rationale**: All failures share the same error message (`No Anthropic-compatible providers configured for model gemini-2.5-flash-lite`). These items have never been summarized and should be retried after the fix.

**SQL**:
```sql
UPDATE contents SET status = 'pending', error_message = NULL
WHERE status = 'failed' AND error_message LIKE '%No Anthropic-compatible providers%';
```

## Risks / Trade-offs

**[Sync/async boundary complexity]** → Mitigated by extracting sync cores (not wrapping async in `asyncio.run()`). The Anthropic and Gemini SDKs are already sync — the async wrappers were cosmetic.

**[Test mock migration]** → Tests currently mock `Anthropic()` or `get_db()`. After refactor, tests for `LLMSummarizationAgent` should mock `LLMRouter.generate_sync()` and DigestReviser tests should mock `LLMRouter.generate_with_tools()`. Risk is low — existing tests primarily test DB operations and JSON parsing, not LLM calls.

**[Response format differences across providers]** → Gemini and OpenAI may format JSON responses differently than Claude. Mitigated by the existing `_extract_json_from_response()` which handles raw JSON and markdown code blocks — this is provider-agnostic already.

**[Cost tracking accuracy]** → `LLMResponse` provides `input_tokens` and `output_tokens` which map directly to the existing `SummarizationAgent` tracking fields. No accuracy loss.
