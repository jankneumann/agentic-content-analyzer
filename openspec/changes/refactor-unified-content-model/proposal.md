# Change: Unify Newsletter and Document into Content Model with Markdown-First Storage

## Why

The current data model has accumulated complexity:

1. **Redundant tables**: Newsletter and Document store overlapping information with an awkward FK relationship (Document.newsletter_id → Newsletter)
2. **Inconsistent content formats**:
   - Newsletter: raw_html, raw_text (unstructured)
   - Document: markdown_content (structured)
   - Summary: executive_summary (text) + key_themes (JSON list) + strategic_insights (JSON list)
   - Digest: executive_overview (text) + strategic_insights (JSON list) + emerging_trends (JSON list)
3. **Chunking complexity**: The search proposal must reference multiple source tables (newsletter, document, summary, digest) with different content fields
4. **Parser output mismatch**: All parsers output markdown via DocumentContent, but Newsletter stores raw_html/raw_text

Unifying to a single Content model with markdown as the canonical format will:
- Simplify the data layer
- Enable consistent chunking and search
- Align storage with parser output
- Support structured UI rendering from markdown

## What Changes

- **Merge Newsletter and Document** into unified `Content` table
- **Adopt markdown as canonical format** for all content types (ingested, summaries, digests)
- **Use embedded references** for structured elements (tables, images) within markdown
- **Migrate existing data** from Newsletter + Document to Content
- **Update Summary and Digest** to use markdown with section conventions
- **Deprecate JSON list fields** in favor of markdown sections

## Impact

- **Affected specs**: New capability (content-model), modifies document-parsing
- **Affected code**:
  - `src/models/content.py` - New unified Content model
  - `src/models/newsletter.py` - Deprecated, migrated
  - `src/models/document.py` - Deprecated, migrated
  - `src/models/summary.py` - Refactored to markdown sections
  - `src/models/digest.py` - Refactored to markdown sections
  - `src/ingestion/` - Updated to create Content records
  - `src/processors/summarizer.py` - Output markdown format
  - `src/processors/digest_creator.py` - Output markdown format
  - `src/api/` - Updated endpoints for Content
  - `alembic/versions/` - Migration to create Content, migrate data, drop old tables
- **Dependencies**: None new
- **Breaking changes**:
  - API response format changes for summaries/digests (JSON lists → markdown)
  - Database schema change (requires migration)

## Status

**~75% Complete** - Core implementation done, migrations run in production.

Completed:
- Database schema and Content model
- All ingestion services updated
- Processors updated for markdown output
- API routes updated with deprecation headers
- Data migration scripts and production migration

Remaining:
- Image model and services (deferred)
- Some integration tests
- Legacy table cleanup (deferred)

## Related Proposals

### API Versioning

The `/api/v1/newsletters` endpoints are already marked deprecated using headers from the `add-api-versioning` pattern. When cleanup phase runs, these endpoints will be sunset.

### Dependencies

- Required by: `add-advanced-document-search` (depends on Content.markdown_content)
- Related: `add-api-versioning` (deprecation headers pattern)
- Related: `content-sharing` (adds fields to Content model)
