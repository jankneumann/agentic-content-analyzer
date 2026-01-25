# Case Studies & Lessons Learned

Historical documentation of major refactoring efforts and lessons learned. This document preserves institutional knowledge from past projects to inform future work.

> **When to read this**: When planning a major refactoring, model migration, or architectural change. The patterns here have been battle-tested.

## Table of Contents

- [Model ID Refactoring (December 2024)](#model-id-refactoring-december-2024)
- [Newsletter → Content Migration (January 2025)](#newsletter--content-migration-january-2025)
- [Multi-Provider LLM Routing (January 2025)](#multi-provider-llm-routing-january-2025)
- [Frontend-Backend API Field Mismatch Debugging (January 2025)](#frontend-backend-api-field-mismatch-debugging-january-2025)
- [Legacy Model Cleanup & Idempotent Migrations (January 2026)](#legacy-model-cleanup--idempotent-migrations-january-2026)
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

> **Historical Note**: The Newsletter model has since been completely removed (January 2026). These lessons remain valuable for understanding the migration patterns and for future similar migrations.

Successfully migrated multiple processors from the legacy Newsletter model to the unified Content model, eliminating foreign key bugs and standardizing data access patterns.

### 1. Root Cause Analysis: Legacy FK References

**Problem**: Processors were querying `newsletter_id` (legacy FK) instead of `content_id` (new FK) in `NewsletterSummary`, causing empty results when Newsletter records didn't exist.

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
- Search for ALL usages of legacy FK before considering migration complete
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

**Approach**: Add warnings to deprecated methods rather than removing them immediately. This allows gradual migration.

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
- Eventually remove the deprecated code entirely (as we did in January 2026)

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

## Frontend-Backend API Field Mismatch Debugging (January 2025)

Diagnosed and fixed three interconnected UX issues in the review pages caused by field name mismatches between frontend TypeScript interfaces and backend API responses.

### 1. The Symptom vs Root Cause Pattern

**Symptoms reported by user**:
1. Navigation arrows in summary review not working
2. AI assistant not responding in summary review
3. Digest showing "123 newsletters" but "none can be displayed"

**Root causes discovered**:
1. Frontend expected `prev_newsletter_id`, backend returned `prev_content_id`
2. Navigation fix cascaded to fix AI assistant (was secondary effect)
3. Backend endpoint queried only legacy `Newsletter` join, not new `Content` model

**Key Learning**: When multiple features break together, look for a shared root cause. The navigation and AI assistant issues were both caused by the same underlying field name mismatch.

### 2. Frontend-Backend Field Name Alignment

**Problem**: After the Newsletter → Content migration, the backend API was updated to return `content_id` fields, but frontend TypeScript interfaces still expected `newsletter_id` fields.

**Before (mismatched)**:
```typescript
// Frontend interface (summaries.ts)
export interface SummaryNavigationInfo {
  prev_newsletter_id: number | null  // ❌ Doesn't match backend
  next_newsletter_id: number | null
}
```

```python
# Backend response (summary_routes.py)
class NavigationResponse(BaseModel):
    prev_content_id: int | None  # ✓ Backend updated correctly
    next_content_id: int | None
```

**After (aligned)**:
```typescript
// Frontend interface updated to match backend
export interface SummaryNavigationInfo {
  prev_content_id: number | null  // ✓ Now matches
  next_content_id: number | null
}
```

**Key Learnings**:
- When migrating models, update BOTH backend responses AND frontend interfaces
- Use grep/search across entire codebase: `grep -r "newsletter_id" web/src/`
- TypeScript won't catch the mismatch - fields become silently `undefined`
- Add integration tests that verify API response structure matches frontend types

### 3. Query Strategy for Dual-Model Support

**Problem**: The digest sources endpoint only queried summaries via `Newsletter` join, failing to find summaries linked to the new `Content` model.

**Original query (broken for Content-linked summaries)**:
```python
summaries = (
    db.query(NewsletterSummary)
    .join(Newsletter)  # ❌ Only finds newsletter-linked summaries
    .filter(Newsletter.published_date >= digest.period_start)
    .all()
)
```

**Solution: Multi-strategy query with fallbacks**:
```python
# Strategy 1: Use source_content_ids if available (new flow)
if digest.source_content_ids:
    summaries = db.query(NewsletterSummary).filter(
        NewsletterSummary.content_id.in_(digest.source_content_ids)
    ).all()

# Strategy 2: Query Content by period (fallback)
if not results:
    summaries = db.query(NewsletterSummary).join(Content).filter(
        Content.published_date.between(period_start, period_end)
    ).all()

# Strategy 3: Legacy Newsletter join (backwards compatibility)
if not results:
    summaries = db.query(NewsletterSummary).join(Newsletter).filter(
        Newsletter.published_date.between(period_start, period_end)
    ).all()
```

**Key Learnings**:
- During model migration, queries must handle BOTH old and new relationships
- Use cascading fallback strategies for backwards compatibility
- Track metadata (like `source_content_ids`) to enable efficient direct lookups
- Eventually remove legacy fallbacks once migration is complete

### 4. URL Parameter Preservation During Navigation

**Problem**: Navigation handlers updated the route but lost the `source=content` query parameter, causing the next page to use wrong data source.

**Before (lost query param)**:
```typescript
navigate({
  to: "/review/summary/$id",
  params: { id: navInfo.prev_content_id.toString() }
  // ❌ Missing search param - defaults to newsletter source
})
```

**After (preserves query param)**:
```typescript
navigate({
  to: "/review/summary/$id",
  params: { id: navInfo.prev_content_id.toString() },
  search: { source: "content" }  // ✓ Maintains content source
})
```

**Key Learnings**:
- When navigating, preserve query parameters that affect data loading
- Review all navigation handlers when changing URL parameter semantics
- Consider using a custom navigation hook that automatically preserves key params

### 5. Debugging Strategy for Multi-Symptom Issues

**Approach used**:
1. **Map symptoms to code paths**: Navigation → ReviewHeader → handlers → API
2. **Compare working vs broken**: Digest review (working) vs Summary review (broken)
3. **Find the divergence point**: Same components, different data loading
4. **Trace data flow end-to-end**: Frontend type → API call → Backend response → Frontend handler

**Diff technique**:
```bash
# Quick comparison to find differences
diff -y <(grep -n "navInfo" digest.$id.tsx) <(grep -n "navInfo" summary.$id.tsx)
```

**Key Learnings**:
- Side-by-side comparison of working vs broken code is highly effective
- The bug is often at the interface boundary (API response ↔ frontend type)
- When symptoms seem unrelated, look for shared dependencies
- Check browser Network tab to see actual API response vs expected structure

### 6. Migration Verification Checklist

Add to your model migration process:

```markdown
## API Interface Verification
- [ ] Backend response model field names updated
- [ ] Frontend TypeScript interfaces updated to match
- [ ] Navigation/routing handlers use correct field names
- [ ] Query parameters preserved during navigation
- [ ] Queries handle both old AND new model relationships
- [ ] Integration tests verify end-to-end data flow
- [ ] Manual testing of affected UI flows
```

---

## Legacy Model Cleanup & Idempotent Migrations (January 2026)

Successfully removed the Newsletter model infrastructure entirely and renamed `newsletter_summaries` table to `summaries`, including handling of complex migration edge cases. The Newsletter model no longer exists in the codebase.

### 1. Isolating Deprecated Models from Shared SQLAlchemy Base

**Problem**: All models imported from a shared `newsletter.py` file, causing SQLAlchemy to auto-register Newsletter tables in new databases even without migrations.

**Impact**: Fresh databases (Neon branches, new Supabase projects) would create legacy `newsletters` table automatically via `Base.metadata.create_all()`.

**Solution**: Create a separate `base.py` file for the shared declarative base:

```python
# src/models/base.py (NEW)
"""SQLAlchemy declarative base - shared by all models."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

```python
# src/models/content.py (UPDATED)
from src.models.base import Base  # Instead of from .newsletter import Base

class Content(Base):
    ...
```

```python
# src/models/newsletter.py (ISOLATED)
from sqlalchemy.orm import declarative_base

# Newsletter uses its OWN Base - not registered with other models
LegacyBase = declarative_base()

class Newsletter(LegacyBase):  # Won't be auto-created
    ...
```

**Key Learnings**:
- SQLAlchemy auto-registers models with `Base.metadata` at import time
- Importing ANY model that shares a Base with deprecated models includes those deprecated tables
- Isolation via separate Base prevents auto-creation in fresh databases
- This is a **zero-migration** fix - no schema changes required

### 2. Renaming Tables with Dependent Objects

**Challenge**: Renaming `newsletter_summaries` to `summaries` required coordinated updates to:
- Table name itself
- All indexes referencing the table
- All foreign key constraints (both inbound and outbound)
- Foreign key references from other tables (like `images`)

**Migration Order Matters**:
```python
def upgrade():
    # Step 1: Drop FKs that reference this table first
    conn.execute(sa.text(
        "ALTER TABLE images DROP CONSTRAINT IF EXISTS images_summary_id_fkey"
    ))

    # Step 2: Drop outbound FKs from the table
    conn.execute(sa.text(
        "ALTER TABLE newsletter_summaries "
        "DROP CONSTRAINT IF EXISTS fk_newsletter_summaries_content_id"
    ))

    # Step 3: Drop indexes (they reference the old table name)
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_newsletter_summaries_content_id"))

    # Step 4: Rename the table
    op.rename_table("newsletter_summaries", "summaries")

    # Step 5: Recreate indexes with new naming
    op.create_index("ix_summaries_content_id", "summaries", ["content_id"])

    # Step 6: Recreate FKs with new naming
    op.create_foreign_key(
        "fk_summaries_content_id", "summaries", "contents",
        ["content_id"], ["id"], ondelete="SET NULL"
    )
```

**Key Learnings**:
- **Drop before rename**: FKs and indexes must be dropped before table rename
- **Recreate after rename**: New FKs/indexes reference new table name
- **Order: inbound FKs → outbound FKs → indexes → rename → recreate**
- PostgreSQL doesn't auto-rename dependent objects

### 3. Writing Idempotent Migrations

**Problem**: Migrations failed when run against databases in partial/different states:
- Index didn't exist (already dropped or never created)
- Column didn't exist (different migration history)
- Table already renamed (migration partially completed)

**Pattern**: Use `IF EXISTS` and existence checks:

```python
def upgrade():
    conn = op.get_bind()

    # Check if source table exists before any operations
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'newsletter_summaries'"
    ))
    if not result.fetchone():
        return  # Already migrated or never existed

    # Use IF EXISTS for drops - safe if already gone
    conn.execute(sa.text(
        "DROP INDEX IF EXISTS ix_newsletter_summaries_content_id"
    ))

    conn.execute(sa.text(
        "ALTER TABLE newsletter_summaries "
        "DROP CONSTRAINT IF EXISTS fk_newsletter_summaries_content_id"
    ))

    # Check column exists before dropping
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'newsletter_summaries' "
        "AND column_name = 'newsletter_id'"
    ))
    if result.fetchone():
        op.drop_column("newsletter_summaries", "newsletter_id")
```

**Key Learnings**:
- **Always use `IF EXISTS`** for drops (indexes, constraints, tables)
- **Query `information_schema`** to check existence before operations that don't support IF EXISTS
- **Return early** if migration already applied (table renamed, etc.)
- **Idempotent migrations** can be safely re-run without errors

### 4. Handling Schema vs Model Drift

**Problem**: Migration tried to create FK constraint on `images.summary_id` column that didn't exist in the database (was defined in model but never migrated).

**Error**:
```
column "summary_id" referenced in foreign key constraint does not exist
```

**Solution**: Conditionally create FKs only when the referenced column exists:

```python
# Step 7: Recreate images FK (only if column exists)
result = conn.execute(sa.text(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name = 'images' AND column_name = 'summary_id'"
))
if result.fetchone():
    op.create_foreign_key(
        "images_summary_id_fkey", "images", "summaries",
        ["summary_id"], ["id"], ondelete="SET NULL"
    )
```

**Key Learnings**:
- **Models and schemas can drift** when migrations aren't generated for all changes
- **Never assume FK target columns exist** - check first
- **Different environments may have different schemas** (dev, staging, prod, feature branches)
- **Conditional FK creation** ensures migration works across all database states

### 5. Backwards Compatibility via Class Aliases

**Challenge**: 61 files referenced `NewsletterSummary` - needed gradual migration path.

**Solution**: Create alias for backwards compatibility:

```python
# src/models/summary.py
class Summary(Base):
    """Content summary database model."""
    __tablename__ = "summaries"
    ...

# Backwards compatibility alias
NewsletterSummary = Summary
```

**Benefits**:
- Existing code continues to work unchanged
- New code uses the new name
- Full rename can happen incrementally

**Key Learnings**:
- **Aliases enable gradual migration** without big-bang changes
- **Both names point to same class** - no duplicate definitions
- **Document the alias** in docstring/comments
- The alias `NewsletterSummary` remains for backwards compatibility but new code should use `Summary`

### 6. Parallel Code Updates with Subagents

**Challenge**: Updating 61 files with consistent changes (import paths, class names, variable names).

**Approach**: Use parallel agents for different file categories:
```
Agent 1: src/ Python files (services, processors, API)
Agent 2: tests/ Python files (fixtures, assertions)
Agent 3: scripts/ Python files (legacy scripts)
Agent 4: web/src/ TypeScript files (type definitions)
```

**Key Learnings**:
- **Categorize files** by type/location for parallel processing
- **Consistent patterns** within each category (tests have fixtures, src has services)
- **Validate after each agent** completes to catch inconsistencies
- **Run linter/type-checker** to find remaining issues

### 7. Migration Testing Checklist

Use this checklist for table rename/cleanup migrations:

```markdown
## Pre-Migration
- [ ] Identify all dependent objects (FKs, indexes, views)
- [ ] Map inbound FK references from other tables
- [ ] List all code references to old table/class names
- [ ] Check for model-schema drift (columns in model but not DB)

## Migration Script
- [ ] Check source table exists before operations
- [ ] Use IF EXISTS for all drops
- [ ] Check column existence before FK creation
- [ ] Proper ordering: drop FKs → drop indexes → rename → recreate
- [ ] Implement downgrade() with reverse ordering

## Code Updates
- [ ] Create backwards-compatible alias
- [ ] Update imports in all files
- [ ] Update foreign key column references
- [ ] Update TypeScript interfaces

## Validation
- [ ] Run migration on fresh database
- [ ] Run migration on existing database
- [ ] Run migration twice (idempotency test)
- [ ] Verify all tests pass
- [ ] Verify API responses use correct field names
```

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
9. **Write idempotent migrations** - Always use `IF EXISTS` and existence checks
10. **Handle schema drift** - Don't assume DB matches model; check before FK operations
11. **Use backwards-compatible aliases** - Enable gradual migration over big-bang changes
12. **Isolate deprecated models** - Separate Base classes prevent unwanted auto-creation
