# Case Studies & Lessons Learned

Historical documentation of major refactoring efforts and lessons learned. This document preserves institutional knowledge from past projects to inform future work.

> **When to read this**: When planning a major refactoring, model migration, or architectural change. The patterns here have been battle-tested.

## Table of Contents

- [Model ID Refactoring (December 2024)](#model-id-refactoring-december-2024)
- [Newsletter → Content Migration (January 2025)](#newsletter--content-migration-january-2025)
- [Multi-Provider LLM Routing (January 2025)](#multi-provider-llm-routing-january-2025)
- [General Refactoring Best Practices](#general-refactoring-best-practices)

---

## Model ID Refactoring (December 2024)

Successfully refactored from dated model IDs to family-based IDs with provider-specific identifiers.

### 1. Database Migrations with Data Transformation

**Challenge**: Transform existing data during schema change (extract version from model IDs)

**Solution**: Use SQL regex in Alembic migration for automatic data transformation:

```python
def upgrade():
    # Add new column
    op.add_column('newsletter_summaries',
        sa.Column('model_version', sa.String(20), nullable=True))

    # Transform existing data using SQL regex
    op.execute("""
        UPDATE newsletter_summaries
        SET model_version = substring(model_used from '(\\d{8})$'),
            model_used = regexp_replace(model_used, '-\\d{8}$', '')
        WHERE model_used ~ '\\d{8}$'
    """)
```

**Key Learnings**:
- Alembic migrations can handle both schema AND data changes in one migration
- PostgreSQL regex functions (`substring`, `regexp_replace`) enable complex transformations
- Always provide `downgrade()` to reverse both schema and data changes
- Test migrations on copy of production data before applying

### 2. Multi-Phase Refactoring Strategy

**Approach**: Break large refactoring into 6 sequential phases:
1. Update data models (backward compatible - adds new fields)
2. Update YAML configuration (breaking change point)
3. Create database migration
4. Update agent and processor code
5. Update all tests
6. Update documentation

**Key Learnings**:
- **Commit after each phase** for easy rollback if issues discovered
- **Run tests after each phase** to validate changes incrementally
- **Sequence matters**: Start with least breaking changes, end with most breaking
- **Phase 1 can be non-breaking**: Adding optional fields maintains backward compatibility
- **Phase 2 identifies breaking point**: YAML restructure breaks existing code
- **Document the plan first**: Created detailed plan in plan mode before executing

**Benefits**:
- Each phase testable independently
- Easy to identify which phase caused issues
- Clear progress tracking (6 phases = 6 commits)
- Rollback is straightforward (revert specific phase)

### 3. Backward Compatibility Sequencing

**Pattern**: Order changes from least to most breaking

**Example sequence**:
```
Phase 1: Add new fields (BACKWARD COMPATIBLE)
  ✅ Old code still works
  ✅ New code can use new fields
  ✅ Safe to deploy incrementally

Phase 2: Change configuration format (BREAKING)
  ❌ Old code breaks
  ✅ Must deploy all at once
  ✅ Database migration ensures data consistency
```

**Key Learnings**:
- Identify the "breaking point" in your refactoring
- Complete all non-breaking changes first
- Coordinate breaking changes in single deployment
- Use feature flags if gradual rollout needed

### 4. Configuration System Design Patterns

**Challenge**: Different providers use different model identifier formats
- Anthropic: `claude-sonnet-4-5-20250929`
- AWS Bedrock: `anthropic.claude-sonnet-4-5-20250929-v1:0`
- Vertex AI: `claude-sonnet-4-5@20250929`

**Solution**: Two-tier ID system
- **User-facing**: Family-based IDs (`claude-sonnet-4-5`)
- **Internal**: Provider-specific IDs (stored in YAML, auto-selected)

**Key Learnings**:
- **Abstract provider differences** from users for better UX
- **Store mappings in configuration** (not code) for easier updates
- **Separate concerns**: General ID for logic, provider ID for API calls
- **Version tracking**: Store both general ID and version separately in database

**Benefits**:
- Users write `claude-sonnet-4-5` everywhere (stable, clean)
- Provider changes don't require code updates
- Can use different versions per provider
- Database tracks exactly what was used

### 5. Documentation Refactoring Triggers

**Observation**: CLAUDE.md grew to 993 lines with single section at 400+ lines

**Decision**: Split into focused `/docs` directory with 6 files

**Key Learnings**:
- **~400 lines per section** is good threshold for splitting
- **Monolithic docs become unmaintainable** around 800-1000 lines
- **Split by concern**, not by size (setup ≠ configuration ≠ guidelines)
- **Refactor proactively** before docs become too large
- **Update main file to index** with links to detailed docs

**Results**:
- Main CLAUDE.md: 993 lines → 155 lines (overview + quick reference)
- 6 focused docs: easier to find, update, and maintain
- Better multi-audience support (beginners vs experts)

### 6. Testing Strategy During Refactoring

**Approach**: Test after each phase, not at the end

**Pattern**:
```bash
# After Phase 1 (data models)
pytest tests/test_config/test_models.py -v
✓ 29 tests passed

# After Phase 2 (YAML config)
python -c "from src.config.models import MODEL_REGISTRY; print(len(MODEL_REGISTRY))"
✓ Loaded 9 models

# After Phase 3 (migration)
alembic upgrade head
pytest tests/test_config/ -v
✓ All tests pass with new schema

# After Phase 4 (code updates)
pytest tests/integration/ -v
✓ Integration tests verify end-to-end flow

# After Phase 5 (test updates)
pytest
✓ Full test suite (108 tests) passes
```

**Key Learnings**:
- **Incremental validation** catches issues early
- **Different test types** for different phases (unit → integration → full)
- **Verify configuration loads** before running full tests
- **Integration tests** ensure all pieces work together after code changes
- **Don't wait until end** to discover Phase 2 broke everything

### 7. Migration Rollback Strategy

**Preparation**: Always implement `downgrade()` in migrations

```python
def downgrade():
    # Reverse data transformation first
    op.execute("""
        UPDATE newsletter_summaries
        SET model_used = model_used || '-' || model_version
        WHERE model_version IS NOT NULL
    """)

    # Then remove columns
    op.drop_column('newsletter_summaries', 'model_version')
```

**Key Learnings**:
- **Data transformation before schema** in downgrade (reverse order of upgrade)
- **Test downgrade** in development before production migration
- **Document rollback plan** in migration comments
- **Preserve data** - concatenate back to original format, don't lose information

---

## Newsletter → Content Migration (January 2025)

Successfully migrated multiple processors from deprecated Newsletter model to unified Content model, eliminating foreign key bugs and standardizing data access patterns.

### 1. Root Cause Analysis: Deprecated FK References

**Problem**: Processors were querying `newsletter_id` (deprecated FK) instead of `content_id` (new FK) in `NewsletterSummary`, causing empty results when Newsletter records didn't exist.

**Symptom**: Theme analysis and digest creation returned empty summaries despite having valid Content records with summaries.

**Solution**: Systematic audit and update of all FK references:
```python
# Before (broken) - NewsletterSummary.newsletter_id is deprecated
summaries = db.query(NewsletterSummary).filter(
    NewsletterSummary.newsletter_id.in_(newsletter_ids)  # ❌ Wrong FK
).all()

# After (correct) - Use NewsletterSummary.content_id
summaries = db.query(NewsletterSummary).filter(
    NewsletterSummary.content_id.in_(content_ids)  # ✅ Correct FK
).all()
```

**Key Learnings**:
- Deprecation warnings don't prevent bugs - code still compiles and runs
- Search for ALL usages of deprecated FK before considering migration complete
- Use `grep -r "newsletter_id"` to find remaining references

### 2. Field Naming Changes Between Models

**Challenge**: Newsletter and Content models use different field names for similar data.

**Mapping Table**:
| Newsletter Model | Content Model | Notes |
|------------------|---------------|-------|
| `raw_text` | `markdown_content` | Primary parsed content |
| `raw_html` | `raw_content` | Original unparsed content |
| `source` | `publication` | Origin publication name |
| `newsletter_ids` | `content_ids` | In tool outputs/metadata |
| `newsletter_ids_fetched` | `content_ids_fetched` | In script records |

**Key Learnings**:
- Create a mapping table before starting migration
- Update ALL usages - not just model access but also variable names, API responses, and metadata
- Test output format explicitly (check JSON keys in API responses)

### 3. LLM Tool Renaming for Agent Processors

**Challenge**: LLM agents have learned tool names - changing them affects prompt effectiveness and requires consistent updates to tool definitions, handlers, and prompts.

**Tool Renames**:
```python
# Tool definitions
"get_newsletter_content" → "get_content"
"fetch_newsletter_content" → "fetch_content"
"search_newsletters" → "search_content"

# Handler dispatch
if tool_name == "get_newsletter_content":  # ❌ Old
if tool_name == "get_content":  # ✅ New

# Prompt instructions
"Use search_newsletters to find..." → "Use search_content to find..."
```

**Key Learnings**:
- Update tool definitions, handler dispatch, AND prompts together
- Tool names in prompts train the LLM - inconsistency confuses the model
- Consider backwards compatibility period for API-exposed tools

### 4. Eager Loading for Detached Session Access

**Problem**: Accessing relationships after SQLAlchemy session closes raises `DetachedInstanceError`.

**Context**: When loading summaries, we need to access `summary.content` outside the session context.

**Solution**: Use `joinedload()` to eager-load relationships:
```python
from sqlalchemy.orm import joinedload

# Before (fails when accessing summary.content outside session)
summaries = db.query(NewsletterSummary).filter(...).all()

# After (content relationship pre-loaded)
summaries = (
    db.query(NewsletterSummary)
    .options(joinedload(NewsletterSummary.content))  # Eager load
    .filter(...)
    .all()
)

# Now safe to access outside session
for summary in summaries:
    title = summary.content.title  # ✅ Works
```

**Key Learnings**:
- Plan for session lifecycle when designing data access
- Use `joinedload()` for relationships accessed in return values
- Consider using `selectinload()` for one-to-many relationships to avoid N+1

### 5. Deprecation Warning Strategy

**Approach**: Add warnings to deprecated methods rather than removing them immediately.

```python
import warnings

def get_newsletters(self):
    """Deprecated: Use get_contents() instead."""
    warnings.warn(
        "get_newsletters() is deprecated. Use get_contents() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return self.get_contents()
```

**Key Learnings**:
- Warnings help identify remaining callers during migration
- Keep deprecated methods working (call the new method internally)
- Set `stacklevel=2` so warning shows caller's line, not the deprecated function
- Plan removal date and communicate to team

### 6. Test Fixture Migration Pattern

**Challenge**: Test fixtures hardcoded Newsletter model assumptions.

**Before**:
```python
@pytest.fixture
def sample_summary():
    return NewsletterSummary(
        newsletter_id=1,  # Deprecated FK
        # ...
    )
```

**After**:
```python
@pytest.fixture
def sample_summary(sample_content):  # Depend on content fixture
    summary = NewsletterSummary(
        content_id=sample_content.id,  # Use content FK
        # ...
    )
    summary.content = sample_content  # Attach for eager-load tests
    return summary
```

**Key Learnings**:
- Update fixtures to use new FKs and attach relationships
- Fixture dependencies should reflect model relationships
- Create content fixtures before summary fixtures
- Explicitly attach relationships for tests that access them

### 7. Systematic Migration Checklist

Use this checklist for model deprecation migrations:

```markdown
## Pre-Migration
- [ ] Document field name mappings (old → new)
- [ ] Identify all FK references with grep/search
- [ ] List all affected processors/services
- [ ] Create test coverage for affected code paths

## Code Updates
- [ ] Update model FK references
- [ ] Update field name access patterns
- [ ] Rename LLM tool definitions
- [ ] Update LLM tool handlers
- [ ] Update prompt instructions mentioning old names
- [ ] Add eager loading where needed
- [ ] Add deprecation warnings to legacy methods

## Testing
- [ ] Update test fixtures
- [ ] Run affected test modules
- [ ] Test API responses for correct field names
- [ ] Test LLM tool calls end-to-end

## Documentation
- [ ] Update CLAUDE.md guidelines
- [ ] Document lessons learned
- [ ] Update API documentation if applicable
```

---

## Multi-Provider LLM Routing (January 2025)

Created a unified `LLMRouter` class to abstract LLM provider differences and enable easy provider switching across all pipeline processors.

### 1. Provider-Agnostic Tool Definitions

**Challenge**: Each LLM provider uses different formats for function/tool calling:
- Anthropic: `input_schema` key, tools list in API call
- Gemini: `FunctionDeclaration` with `parameters` property
- OpenAI: `function` wrapper with `parameters` schema

**Solution**: Create a provider-agnostic `ToolDefinition` dataclass:
```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format

# Usage in processors
PODCAST_TOOLS = [
    ToolDefinition(
        name="get_content",
        description="Retrieve content by ID...",
        parameters={
            "type": "object",
            "properties": {"content_id": {"type": "integer"}},
            "required": ["content_id"],
        },
    ),
]
```

**Key Learnings**:
- Use JSON Schema as the universal parameter format (all providers support it)
- Convert to provider-specific format at the router level, not in processors
- Keep tool definitions with the processors that use them, not in the router

### 2. Dual Parameterization: Model AND Provider

**Challenge**: Users need control over both model choice AND provider (same model can be served by multiple providers).

**Example**: `claude-sonnet-4-5` available via:
- Anthropic direct API
- AWS Bedrock
- Google Vertex AI

**Solution**: Make provider explicitly configurable with sensible defaults:
```python
class LLMRouter:
    DEFAULT_PROVIDERS = {
        ModelFamily.CLAUDE: Provider.ANTHROPIC,
        ModelFamily.GEMINI: Provider.GOOGLE_AI,
        ModelFamily.GPT: Provider.OPENAI,
    }

    def resolve_provider(
        self,
        model: str,
        provider: Provider | None = None
    ) -> Provider:
        """Return explicit provider or infer from model family."""
        if provider is not None:
            return provider  # Explicit choice honored

        family = ModelRegistry.get_family(model)
        return self.DEFAULT_PROVIDERS.get(family, Provider.ANTHROPIC)
```

**Key Learnings**:
- Don't force users to specify provider if they don't care
- Always allow explicit override for when defaults don't apply
- Provider-specific model IDs should be in configuration, not code

### 3. API Rate Limit Mitigation Through Provider Switching

**Problem**: Anthropic API returned 529 (Overloaded) and 429 (Rate Limit: 30k tokens/min) errors during script generation.

**Symptoms**:
- Script generation reported "successful but empty"
- Backend logs showed API errors, but generation loop continued
- Default retry logic insufficient for sustained load

**Solution**: Switch to provider with higher rate limits:
```yaml
# model_registry.yaml
defaults:
  # Before: claude-sonnet-4-5 (30k tokens/min on Anthropic)
  podcast_script: gemini-2.5-flash  # Higher rate limits
```

**Key Learnings**:
- Different providers have vastly different rate limits
- Gemini's rate limits are generally higher for equivalent tasks
- Configuration-based model selection enables quick mitigation
- Monitor backend logs for API errors - they may not surface to frontend
- Consider implementing automatic provider fallback for resilience

### 4. Agentic Loop Abstraction

**Challenge**: Implementing tool-calling loops varies significantly by provider:
- Anthropic: `tool_use` blocks with `tool_use_id`
- Gemini: `function_call` parts requiring `FunctionResponse`
- OpenAI: `tool_calls` with `tool_call_id`

**Solution**: Unified interface hiding provider differences:
```python
async def generate_with_tools(
    self,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[ToolDefinition],
    tool_executor: Callable[[str, dict], Any],
    provider: Provider | None = None,
) -> LLMResponse:
    """Run agentic loop with tool calling until completion."""

    # Router handles:
    # 1. Converting ToolDefinition to provider format
    # 2. Making API calls with correct structure
    # 3. Parsing tool calls from response
    # 4. Formatting tool results for next iteration
    # 5. Detecting completion (no more tool calls)
```

**Key Learnings**:
- Agentic loop structure is similar across providers - abstract it once
- Tool executor callback keeps business logic in processors
- Return structured `LLMResponse` with both content and metadata

### 5. CSS Overflow Handling in Select Components

**Problem**: Long titles in Select dropdown (dialog context) caused layout overflow - white background didn't resize properly.

**Context**: React dialogs with Radix UI Select components displaying digest/script titles.

**Solution**: Constrain width and truncate text:
```tsx
// Constrain dropdown to dialog width minus padding
<SelectContent className="max-w-[calc(500px-3rem)]">
  {items.map((item) => (
    <SelectItem key={item.id} value={String(item.id)} className="max-w-full">
      {/* Truncate long titles with ellipsis */}
      <span className="truncate">
        [{item.id}] {item.title}
      </span>
    </SelectItem>
  ))}
</SelectContent>
```

**Key Learnings**:
- `max-w-[calc(container - padding)]` constrains dropdown to parent bounds
- `truncate` class adds `text-overflow: ellipsis` and `overflow: hidden`
- Wrap text content in `<span className="truncate">` for reliable truncation
- `max-w-full` on SelectItem ensures it respects parent constraints

---

## General Refactoring Best Practices

From the above case studies and other refactorings:

1. **Plan first, code second** - Write detailed plan in plan mode
2. **Break into phases** - 4-6 phases ideal for large refactorings
3. **Commit per phase** - Each phase = 1 commit for easy rollback
4. **Test incrementally** - Validate after each phase, not at end
5. **Sequence by risk** - Non-breaking changes first, breaking changes last
6. **Update tests early** - Don't leave test updates for last phase
7. **Document as you go** - Update docs in final phase while context fresh
8. **Review the plan** - Check success criteria match actual implementation
