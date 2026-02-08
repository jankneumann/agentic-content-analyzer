## Context

LLM prompts are scattered across ~9 processor/agent files as Python string constants. A `PromptService` and `prompt_overrides` table already exist and are wired to chat prompts and the settings API, but pipeline processors bypass them entirely. The goal is to close this gap so all prompts flow through one service, are stored/overridden in the database, seeded from a YAML file, and manageable via the UI and CLI.

**Stakeholders**: Pipeline operators (CLI), content reviewers (web UI), developers (prompts.yaml).

**Constraints**:
- Zero behavior change on first deploy — prompts.yaml must contain byte-identical text to the current hardcoded strings.
- Pipeline processors must remain functional without a database (fallback to YAML defaults).
- Template interpolation must be safe (no arbitrary code execution).

## Goals / Non-Goals

**Goals**:
- All LLM prompts loaded via `PromptService` with DB override support
- Template variable interpolation for runtime values (`{title}`, `{content}`, `{period}`)
- Prompt versioning for audit trail
- CLI commands to list, view, edit, reset, export, and import prompts
- Frontend prompt editor on the Settings page
- Automatic seeding from `prompts.yaml` on first access

**Non-Goals**:
- A/B testing of prompts (future work)
- Per-user prompt customization (single-tenant system)
- Prompt chaining or orchestration logic
- Changing the actual prompt content (this proposal is about making them configurable, not rewriting them)

## Decisions

### Decision 1: Template engine — Python `str.format_map()` with safe dict

**What**: Use Python's built-in `str.format_map()` with a `SafeDict` that returns the placeholder unchanged for missing keys, rather than introducing Jinja2.

**Why**: The current prompts use simple `{variable}` placeholders (f-strings). Converting to `str.format_map()` requires minimal changes. Jinja2 adds a dependency, template syntax complexity, and potential security concerns with untrusted input.

**Alternatives considered**:
- Jinja2: More powerful but overkill for simple variable substitution. Introduces sandboxing concerns if users edit templates via UI.
- f-strings with `eval()`: Security risk, rejected.
- No interpolation (force full prompt rewrite): Poor UX for prompts with dynamic sections.

**Implementation**:
```python
class SafeDict(dict):
    """Returns placeholder unchanged for missing keys."""
    def __missing__(self, key):
        return "{" + key + "}"

# Usage in PromptService
def render(self, key: str, **variables) -> str:
    template = self._get_prompt(key, ...)
    return template.format_map(SafeDict(variables))
```

### Decision 2: Prompt key schema — `{category}.{step}.{name}`

**What**: Keep the existing dot-separated key format already used by `PromptService`. Extend it to cover all pipeline prompts.

**Keys**:
- `chat.{artifact_type}.system` — chat assistant system prompts (existing)
- `pipeline.{step}.system` — pipeline system prompts
- `pipeline.{step}.user_template` — pipeline user prompt templates with `{variables}`
- `pipeline.{step}.{variant}` — step-specific variants (e.g., `pipeline.podcast_script.length_brief`)

**Why**: Consistent with the existing implementation. The settings API already parses this format.

### Decision 3: Versioning — Add `version` column to `prompt_overrides`

**What**: Add an auto-incrementing `version` integer to the `prompt_overrides` table. Each update bumps the version. No separate history table.

**Why**: Lightweight audit trail without the complexity of a full changelog table. If full history is needed later, it can be added.

**Schema change**:
```sql
ALTER TABLE prompt_overrides ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE prompt_overrides ADD COLUMN description TEXT;
```

**Alternatives considered**:
- Full history table (`prompt_override_history`): More storage, more queries, deferred to future if needed.
- No versioning: Makes it impossible to track when/why a prompt was changed.

### Decision 4: Processor integration pattern — Constructor injection

**What**: Each processor receives an optional `PromptService` instance. If not provided, one is created with no DB session (YAML defaults only). Prompts are fetched in the method that builds the LLM call.

**Why**:
- Backward compatible — existing callers don't need to change.
- Testable — tests can inject a mock PromptService.
- Consistent with existing patterns (processors already accept optional `ModelConfig`).

**Example**:
```python
class PodcastScriptGenerator:
    def __init__(self, model_config=None, model=None, prompt_service=None):
        self.prompt_service = prompt_service or PromptService()
        # ...

    async def _generate_script_with_anthropic(self, context, request):
        system_prompt = self.prompt_service.get_pipeline_prompt("podcast_script", "system")
        # ... use system_prompt instead of PODCAST_SCRIPT_SYSTEM_PROMPT constant
```

### Decision 5: prompts.yaml as seed, not truth

**What**: `prompts.yaml` is the seed file. On first access of a key, if no DB override exists, the YAML value is used directly (without writing to DB). The DB only stores explicit user overrides.

**Why**:
- Developers update prompts.yaml in code → deploys pick up new defaults automatically.
- Users override via DB → their customizations persist across deploys.
- No startup migration needed — seeding is lazy.
- `reset` operation = delete DB override → falls back to current YAML default.

**Alternatives considered**:
- Eager seeding at startup (write all YAML to DB): Creates drift risk — code changes to YAML wouldn't take effect until DB rows are deleted.
- DB as sole truth (no YAML): Loses version-controlled defaults, makes fresh deployments harder.

### Decision 6: Frontend prompt editor — Textarea with diff view

**What**: On the Settings page, add a "Prompt Configuration" section with:
- Collapsible list of prompts grouped by category
- Click to expand shows a textarea editor
- "Show diff" toggle to compare current value against default
- Save and Reset-to-default buttons
- Override indicator badge

**Why**: Prompts are long-form text. A simple textarea with diff is the minimal useful UI. A full code editor (Monaco) is overkill for prompt text.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Prompt text mismatch during migration | Automated test that compares prompts.yaml entries against current hardcoded strings |
| Users break prompts with bad edits | Reset-to-default button always available; validation that template variables are preserved |
| Performance: DB query per prompt per LLM call | PromptService already caches YAML; DB overrides are small table, single indexed lookup |
| Template variable injection | `SafeDict` only substitutes known keys; no `eval()` or Jinja2 |
| Large prompts in DB text column | PostgreSQL TEXT has no practical limit; this is fine |

## Migration Plan

1. **Expand `prompts.yaml`** with exact copies of hardcoded prompts (verified by test)
2. **Add `version` + `description` columns** via Alembic migration
3. **Update processors** one-by-one to use `PromptService`, keeping old constants as fallback during transition
4. **Remove old constants** after all processors are wired
5. **Add CLI commands** (`aca prompts list/show/set/reset/export/import`)
6. **Build frontend** prompt editor on Settings page
7. **Rollback**: If issues arise, processors fall back to YAML defaults automatically (no DB override = YAML value)

## Open Questions

1. Should prompts support Markdown formatting in the editor (preview mode)?
2. Should there be a "test prompt" feature that runs a prompt against sample content before saving?
3. Should prompt export/import support migrating overrides between environments (e.g., staging → production)?
