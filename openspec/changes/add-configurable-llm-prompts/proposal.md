# Change: Make LLM Prompts Configurable via Database, Settings UI, and CLI

## Why

LLM prompts are currently hardcoded across multiple processor files (`summarizer.py`, `digest_creator.py`, `theme_analyzer.py`, `podcast_script_generator.py`, `script_reviser.py`, `digest_reviser.py`, `historical_context.py`). While a `PromptService` and `prompt_overrides` database table already exist, they are only wired into the **chat assistant** prompts. The pipeline processors ignore the PromptService entirely and embed their prompts as Python string constants.

This means:
- Changing a summarization prompt requires a code change and redeployment
- Users cannot iterate on prompt quality without developer involvement
- There is no UI or CLI for managing prompts used in the core pipeline
- The `prompts.yaml` seed file exists but its `pipeline.*` entries are never consumed by the actual processors

## What Changes

### Phase 1: Wire processors to PromptService (Backend)
- **Extend `prompts.yaml`** with the full, production-quality prompts currently hardcoded in processor files (not the abbreviated placeholders currently there)
- **Update all processors** to load prompts via `PromptService` instead of using inline string constants
- **Add template variable support** to `PromptService` for prompts that require runtime interpolation (e.g., `{period}`, `{word_count_target}`)
- **Add prompt versioning** to the `prompt_overrides` table so changes can be audited

### Phase 2: CLI prompt management
- **Add `aca prompts` CLI subcommand group** with `list`, `show`, `set`, `reset`, and `export/import` commands
- Allow operators to view, customize, and reset prompts from the terminal

### Phase 3: Frontend settings page
- **Build Prompt Configuration section** on the existing Settings page (`web/src/routes/settings.tsx`)
- Provide a prompt editor with diff view (current vs. default), save, and reset-to-default functionality
- List prompts by category (chat, pipeline) with override indicators

### Phase 4: Seed & sync mechanism
- **Automatic seeding**: On application startup, if a prompt key from `prompts.yaml` has no database row, seed it as the default (lazy, on first access)
- **Export/import**: CLI commands to export current prompts to YAML and import from YAML (for environment migration)

## Impact

- Affected specs: `pipeline`, `cli-interface`, new `prompt-management`
- Affected code:
  - `src/services/prompt_service.py` — template variable support, versioning
  - `src/config/prompts.yaml` — expand with full production prompts
  - `src/processors/summarizer.py` — use PromptService
  - `src/processors/digest_creator.py` — use PromptService
  - `src/processors/theme_analyzer.py` — use PromptService
  - `src/processors/podcast_script_generator.py` — use PromptService
  - `src/processors/script_reviser.py` — use PromptService
  - `src/processors/digest_reviser.py` — use PromptService
  - `src/processors/historical_context.py` — use PromptService
  - `src/agents/base.py` — use PromptService for `_create_content_prompt`
  - `src/agents/claude/summarizer.py` — use PromptService for feedback prompt
  - `src/models/settings.py` — add version column to PromptOverride
  - `src/cli/` — new `prompts` command group
  - `web/src/routes/settings.tsx` — prompt management UI
  - `alembic/versions/` — migration for version column
- **BREAKING**: None. Existing behavior is preserved; prompts.yaml seeds provide the same text currently hardcoded.
- Risk: Prompt text changes during migration must be verified to be byte-identical to avoid unintended behavior changes.

## Current State Analysis

### What exists today
| Component | Status | Notes |
|-----------|--------|-------|
| `prompt_overrides` DB table | Exists | Migration `3697508e93f1`, has `id`, `key`, `value`, `created_at`, `updated_at` |
| `PromptOverride` SQLAlchemy model | Exists | In `src/models/settings.py` |
| `PromptService` | Exists | Loads from `prompts.yaml`, checks DB overrides, has `get_chat_prompt` and `get_pipeline_prompt` |
| `src/config/prompts.yaml` | Exists | Has chat prompts (used) and pipeline prompts (abbreviated, unused) |
| Settings API (`/api/v1/settings/prompts`) | Exists | CRUD for prompt overrides with admin key auth |
| Settings page (frontend) | Exists | Placeholder "coming in Phase 3" cards |
| CLI prompt commands | Missing | No `aca prompts` subcommand |
| Processor integration | Missing | All processors use hardcoded string constants |

### Hardcoded prompts inventory (to be moved to prompts.yaml)
| File | Prompt constant/method | Lines | Key to assign |
|------|----------------------|-------|---------------|
| `src/agents/base.py` | `_create_content_prompt()` | 119-184 | `pipeline.summarization.user_template` |
| `src/agents/claude/summarizer.py` | `_create_content_feedback_prompt()` | 372-440 | `pipeline.summarization.feedback_template` |
| `src/processors/digest_creator.py` | system prompt (inline) | ~varies | `pipeline.digest_creation.system` |
| `src/processors/theme_analyzer.py` | system prompt (inline) | ~varies | `pipeline.theme_analysis.system` |
| `src/processors/podcast_script_generator.py` | `PODCAST_SCRIPT_SYSTEM_PROMPT` | 50-116 | `pipeline.podcast_script.system` |
| `src/processors/podcast_script_generator.py` | `PODCAST_SCRIPT_LENGTH_PROMPTS` | 119-164 | `pipeline.podcast_script.length_brief`, `.length_standard`, `.length_extended` |
| `src/processors/script_reviser.py` | `SECTION_REVISION_SYSTEM_PROMPT` | 27-49 | `pipeline.script_revision.system` |
| `src/processors/digest_reviser.py` | `_build_messages()` inline | 401-461 | `pipeline.digest_revision.system` |
| `src/processors/historical_context.py` | `_analyze_evolution_with_llm()` inline | 242-276 | `pipeline.historical_context.evolution_template` |
