# Change: Deprecate Newsletter Model in Favor of Content

## Why

The unified `Content` model was introduced to replace the legacy `Newsletter` model, providing:
- Support for multiple content sources (Gmail, RSS, YouTube, file uploads, webpages)
- Markdown-first storage optimized for LLM consumption
- Better deduplication and canonical content handling

However, the codebase still has 29+ files importing `Newsletter`, duplicate frontend routes (`/newsletters` and `/contents`), and parallel API endpoints. This creates confusion, maintenance burden, and potential for bugs when both models drift out of sync.

## What Changes

### Phase 1: Soft Deprecation (No Dependencies)
- Remove "Newsletters" from frontend navigation sidebar
- Add deprecation banner to `/newsletters` route with link to `/contents`
- Add `@deprecated` JSDoc comments to TypeScript types in `newsletter.ts`
- Add Python deprecation warnings to Newsletter model imports

### Phase 2: Backend Migration (Depends on T0)
- **BREAKING**: Remove dual-write code paths
- Update `NewsletterSummary.newsletter_id` FK to `content_id`
- Migrate remaining Newsletter references in processors/ingestion
- Remove deprecated Newsletter API endpoints

### Phase 3: Frontend Removal (Depends on Phase 2)
- **BREAKING**: Remove `/newsletters` route entirely
- Add HTTP 301 redirect from `/newsletters` → `/contents`
- Remove `newsletter.ts` types (or convert to aliases)
- Update all frontend components to use Content types

### Phase 4: Model Cleanup (Depends on Phase 3 + Production Verification)
- Remove `Newsletter` SQLAlchemy model
- Create migration to drop `newsletters` table (with backup)
- Remove `newsletter_routes.py` API file
- Update all documentation

## Impact

- **Affected specs**: content-ingestion, content-processing, api-endpoints
- **Affected code**:
  - Frontend: `web/src/routes/newsletters.tsx`, `web/src/types/newsletter.ts`
  - Backend: `src/models/newsletter.py`, `src/api/newsletter_routes.py`
  - Processors: `src/processors/summarizer.py`, `src/processors/digest_creator.py`
  - Ingestion: `src/ingestion/gmail.py`, `src/ingestion/substack.py`
- **Breaking changes**: Phase 2-4 are breaking for any external integrations using Newsletter APIs
- **Migration path**: Content model already contains all Newsletter data; no data migration needed
