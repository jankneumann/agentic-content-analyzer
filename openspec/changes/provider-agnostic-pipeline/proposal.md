## Why

Pipeline steps (summarization, digest revision) are hardcoded to Anthropic SDK providers, preventing use of Gemini or OpenAI models. Setting `MODEL_SUMMARIZATION=gemini-2.5-flash-lite` caused all 1,568 content items to fail with "No Anthropic-compatible providers configured." The `LLMRouter` already supports all 6 providers but `ClaudeAgent` and `DigestReviser` bypass it with Anthropic-only client creation. This blocks cost optimization (Gemini Flash Lite is significantly cheaper than Claude Haiku) and prevents free model selection per pipeline step.

## What Changes

- **Refactor `ClaudeAgent` to route through `LLMRouter`** instead of creating Anthropic SDK clients directly. Remove the hardcoded provider filter that rejects Google AI and OpenAI providers. Rename to `LLMSummarizationAgent` (keep `ClaudeAgent` as backward-compat alias).
- **Add `LLMRouter.generate_sync()`** — a synchronous entry point that reuses existing provider-specific generation logic. Needed because `SummarizationAgent.summarize_content()` is synchronous while `LLMRouter.generate()` is async.
- **Refactor `DigestReviser` to use `LLMRouter`** instead of direct `Anthropic()` client. Use `LLMRouter.generate_with_tools()` for the agentic revision loop, replacing the manual Anthropic tool-use implementation.
- **Reset failed content items** — mark 1,568 items with the provider error back to `pending` status for reprocessing.

## Capabilities

### New Capabilities

- `llm-provider-routing`: Unified provider-agnostic LLM routing for all pipeline steps, including sync generation support and automatic provider resolution from model family.

### Modified Capabilities

- `pipeline`: Summarization and digest revision steps now support any configured provider (Anthropic, Google AI, OpenAI, Bedrock, Vertex, Azure) instead of Anthropic-only.

## Impact

- **Code**: `src/agents/claude/summarizer.py`, `src/services/llm_router.py`, `src/processors/digest_reviser.py`, `src/agents/base.py`
- **Tests**: Agent and processor tests need mock updates (mock `LLMRouter` instead of `Anthropic()`)
- **Configuration**: No changes — `MODEL_*` env vars and `model_registry.yaml` already support all providers
- **Data**: 1,568 failed content items reset to pending for reprocessing
- **Breaking**: None — `ClaudeAgent` alias preserved, all public APIs unchanged
