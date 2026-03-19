## 1. LLMRouter sync generation

- [x] 1.1 Add `_generate_anthropic_sync()` to `LLMRouter` — extract sync body from `_generate_anthropic()` (`src/services/llm_router.py`)
- [x] 1.2 Add `_generate_gemini_sync()` to `LLMRouter` — extract sync body from `_generate_gemini()` (`src/services/llm_router.py`)
- [x] 1.3 Add `_get_openai_sync_client()` and `_generate_openai_sync()` — sync `OpenAI`/`AzureOpenAI` client (`src/services/llm_router.py`)
- [x] 1.4 Add `generate_sync()` public method — routes to sync helpers, includes telemetry tracing (`src/services/llm_router.py`)
- [x] 1.5 Add unit tests for `generate_sync()` — mock SDK clients, verify provider routing and LLMResponse fields (`tests/test_services/test_llm_router.py`)

## 2. Refactor ClaudeAgent to LLMSummarizationAgent

- [x] 2.1 Create `LLMRouter` in constructor, replace `_get_client()` with router delegation (`src/agents/claude/summarizer.py`)
- [x] 2.2 Extract shared `_generate_summary()` helper from `summarize_content()` and `summarize_content_with_feedback()` — deduplicate ~90% shared code (`src/agents/claude/summarizer.py`)
- [x] 2.3 Remove `compatible_providers` filter and direct Anthropic SDK imports (`src/agents/claude/summarizer.py`)
- [x] 2.4 Rename class to `LLMSummarizationAgent`, add `ClaudeAgent` backward-compat alias (`src/agents/claude/summarizer.py`)
- [x] 2.5 Update `__init__.py` exports — export both `LLMSummarizationAgent` and `ClaudeAgent` (`src/agents/claude/__init__.py`)
- [x] 2.6 Update agent tests — mock `LLMRouter.generate_sync()` instead of Anthropic SDK (`tests/test_agents/test_claude_agent.py`)

## 3. Refactor DigestReviser to use LLMRouter

- [x] 3.1 Create `LLMRouter` in constructor, remove `from anthropic import Anthropic` (`src/processors/digest_reviser.py`)
- [x] 3.2 Convert `_get_tool_definitions()` to return `ToolDefinition` objects instead of Anthropic-format dicts (`src/processors/digest_reviser.py`)
- [x] 3.3 Create `_execute_tool()` async wrapper compatible with `ToolExecutor` type alias (`src/processors/digest_reviser.py`)
- [x] 3.4 Replace manual agentic loop in `revise_section()` with `LLMRouter.generate_with_tools()` (`src/processors/digest_reviser.py`)
- [x] 3.5 Update `_parse_revision_result()` to accept `LLMResponse` instead of Anthropic response object (`src/processors/digest_reviser.py`)
- [x] 3.6 Update DigestReviser tests — mock `LLMRouter.generate_with_tools()` (`tests/test_processors/test_digest_reviser.py`)

## 4. Reset failed content items

- [ ] 4.1 Reset 1,568 failed content items to `pending` status — SQL: `UPDATE contents SET status='pending', error_message=NULL WHERE status='failed' AND error_message LIKE '%No Anthropic-compatible providers%'`
- [ ] 4.2 Clean up associated failed jobs — SQL: `DELETE FROM pgqueuer_jobs WHERE status='failed'`

## 5. Verification

- [x] 5.1 Run existing test suite — `pytest tests/test_agents/ tests/test_processors/test_summarizer.py tests/test_processors/test_digest_reviser.py -v`
- [ ] 5.2 Run full test suite — `pytest` (ensure no regressions)
- [ ] 5.3 Smoke test with Gemini model — set `MODEL_SUMMARIZATION=gemini-2.5-flash-lite`, run `aca summarize pending --limit 1`
