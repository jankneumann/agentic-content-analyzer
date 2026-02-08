## 1. Database Schema & PromptService Enhancements

- [ ] 1.1 Create Alembic migration to add `version` (integer, default 1) and `description` (text, nullable) columns to `prompt_overrides` table
- [ ] 1.2 Update `PromptOverride` model in `src/models/settings.py` with `version` and `description` fields
- [ ] 1.3 Add `render()` method to `PromptService` for template variable interpolation using `SafeDict` + `str.format_map()`
- [ ] 1.4 Update `set_override()` to auto-increment `version` on updates
- [ ] 1.5 Write unit tests for `PromptService.render()` with known/unknown/missing variables
- [ ] 1.6 Write unit tests for version auto-increment behavior

## 2. Expand prompts.yaml with Production Prompts

- [ ] 2.1 Extract the full summarization prompt from `src/agents/base.py:_create_content_prompt()` into `prompts.yaml` under `pipeline.summarization.user_template`
- [ ] 2.2 Extract the feedback summarization prompt from `src/agents/claude/summarizer.py:_create_content_feedback_prompt()` into `pipeline.summarization.feedback_template`
- [ ] 2.3 Extract `PODCAST_SCRIPT_SYSTEM_PROMPT` from `src/processors/podcast_script_generator.py` into `pipeline.podcast_script.system`
- [ ] 2.4 Extract `PODCAST_SCRIPT_LENGTH_PROMPTS` (brief, standard, extended) into `pipeline.podcast_script.length_brief`, `.length_standard`, `.length_extended`
- [ ] 2.5 Extract `SECTION_REVISION_SYSTEM_PROMPT` from `src/processors/script_reviser.py` into `pipeline.script_revision.system`
- [ ] 2.6 Extract digest revision system prompt from `src/processors/digest_reviser.py:_build_messages()` into `pipeline.digest_revision.system`
- [ ] 2.7 Extract historical context evolution prompt from `src/processors/historical_context.py:_analyze_evolution_with_llm()` into `pipeline.historical_context.evolution_template`
- [ ] 2.8 Extract/verify digest creation system prompt in `pipeline.digest_creation.system`
- [ ] 2.9 Extract/verify theme analysis system prompt in `pipeline.theme_analysis.system`
- [ ] 2.10 Write automated test that verifies prompts.yaml entries match the original hardcoded strings (byte-identical check)

## 3. Wire Processors to PromptService

- [ ] 3.1 Update `SummarizationAgent` base class (`src/agents/base.py`) to accept optional `PromptService` and use it in `_create_content_prompt()`
- [ ] 3.2 Update `ClaudeAgent` (`src/agents/claude/summarizer.py`) to use `PromptService` for `_create_content_feedback_prompt()`
- [ ] 3.3 Update `PodcastScriptGenerator` (`src/processors/podcast_script_generator.py`) to load system and length prompts from `PromptService`
- [ ] 3.4 Update `PodcastScriptReviser` (`src/processors/script_reviser.py`) to load revision system prompt from `PromptService`
- [ ] 3.5 Update `DigestReviser` (`src/processors/digest_reviser.py`) to load revision system prompt from `PromptService`
- [ ] 3.6 Update `HistoricalContextAnalyzer` (`src/processors/historical_context.py`) to load evolution prompt from `PromptService`
- [ ] 3.7 Update digest creator (`src/processors/digest_creator.py`) to load prompts from `PromptService`
- [ ] 3.8 Update theme analyzer (`src/processors/theme_analyzer.py`) to load prompts from `PromptService`
- [ ] 3.9 Remove old hardcoded prompt constants from all processor files
- [ ] 3.10 Write integration tests verifying processors use PromptService and respect DB overrides

## 4. CLI Prompt Management Commands

- [ ] 4.1 Create `src/cli/prompts.py` with `aca prompts` command group
- [ ] 4.2 Implement `aca prompts list` with category filter and override indicators
- [ ] 4.3 Implement `aca prompts show <key>` with full prompt display and version info
- [ ] 4.4 Implement `aca prompts set <key> --value/--file` for setting overrides
- [ ] 4.5 Implement `aca prompts reset <key>` for clearing overrides
- [ ] 4.6 Implement `aca prompts export --output <file>` for YAML export
- [ ] 4.7 Implement `aca prompts import --file <file>` for YAML import
- [ ] 4.8 Register commands in CLI entrypoint
- [ ] 4.9 Write tests for CLI prompt commands

## 5. Frontend Prompt Editor

- [ ] 5.1 Create API client functions for prompt endpoints in `web/src/lib/api/`
- [ ] 5.2 Create TanStack Query hooks for prompt CRUD operations
- [ ] 5.3 Build `PromptEditor` component with textarea, diff view toggle, save/reset buttons
- [ ] 5.4 Build `PromptList` component with category grouping and override badges
- [ ] 5.5 Add "Prompt Configuration" section to Settings page (`web/src/routes/settings.tsx`)
- [ ] 5.6 Write E2E tests for prompt management UI (mock API responses)

## 6. Documentation & Verification

- [ ] 6.1 Update `CLAUDE.md` with prompt management commands and configuration
- [ ] 6.2 Run full test suite (`pytest`) and fix any failures
- [ ] 6.3 Run frontend tests (`cd web && pnpm test:e2e`) and fix any failures
- [ ] 6.4 Verify all processors produce identical output with prompts loaded from YAML vs. old hardcoded strings
