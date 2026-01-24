# Implementation Tasks

## Task Dependencies

```
Phase 1 (Soft Deprecation)     ──── No dependencies, can start immediately
        │
        ▼
Phase 2 (Backend Migration)    ──── Depends on: T0-REFactor-ContentModel (complete)
        │
        ▼
Phase 3 (Frontend Removal)     ──── Depends on: Phase 2
        │
        ▼
Phase 4 (Model Cleanup)        ──── Depends on: Phase 3 + 2 weeks production verification
```

---

## Phase 1: Soft Deprecation ✅

**Dependencies**: None - can start immediately
**Status**: Complete

### 1.1 Frontend Navigation
- [x] 1.1.1 Remove "Newsletters" link from sidebar navigation in `web/src/lib/navigation.ts`
- [x] 1.1.2 Keep route accessible for direct URL access (don't break bookmarks)

### 1.2 Deprecation Banner
- [x] 1.2.1 Create `DeprecationBanner` component in `web/src/components/ui/deprecation-banner.tsx`
- [x] 1.2.2 Add banner to top of `newsletters.tsx` with message and link to `/contents`
- [x] 1.2.3 Style banner with warning colors (amber/yellow)

### 1.3 TypeScript Deprecation
- [x] 1.3.1 Add `@deprecated` JSDoc to all exports in `web/src/types/newsletter.ts`
- [x] 1.3.2 Add `@deprecated` JSDoc to Newsletter hooks in `web/src/hooks/` (N/A - no hooks exist)
- [x] 1.3.3 Update IDE to show deprecation strikethrough (N/A - default behavior with @deprecated)

### 1.4 Python Deprecation Warnings
- [x] 1.4.1 Add `warnings.warn()` to `src/models/newsletter.py` module level
- [x] 1.4.2 Add deprecation docstring to `src/models/newsletter.py`
- [x] 1.4.3 Update `src/models/__init__.py` docstring to mark Newsletter as deprecated

### 1.5 Documentation
- [x] 1.5.1 Update CLAUDE.md to emphasize Content over Newsletter
- [x] 1.5.2 Add deprecation notice to any Newsletter-related docs (in model docstrings)

---

## Phase 2: Backend Migration ✅

**Dependencies**: T0-REFactor-ContentModel must be complete (tasks 10.1-10.4)
**Status**: Complete

### 2.1 Remove Dual-Write Code
- [x] 2.1.1 Identify all dual-write locations - API routes already use ContentIngestionService
- [x] 2.1.2 Gmail ingestion uses GmailContentIngestionService (legacy class retained for reference)
- [x] 2.1.3 RSS ingestion uses RSSContentIngestionService (legacy class retained)
- [x] 2.1.4 YouTube ingestion CLI uses YouTubeContentIngestionService
- [x] 2.1.5 File upload uses FileContentIngestionService

### 2.2 Update Foreign Key References
- [x] 2.2.1 content_id column exists (migration `5a65cf4fe7b6`)
- [x] 2.2.2 Data migration populates content_id from newsletter_id via source_id join
- [x] 2.2.3 Made newsletter_id nullable (migration `c9d0e1f2a3b4`)
- [x] 2.2.4 Added Content relationship to NewsletterSummary model

### 2.3 Update Processors
- [x] 2.3.1 summarizer.py has `summarize_content()` method using content_id
- [x] 2.3.2 digest_creator.py has `_fetch_contents()` method (done in T0)
- [x] 2.3.3 theme_analyzer.py has Content support (done in T0)
- [x] 2.3.4 Historical context supports Content model (done in T0)

### 2.4 Deprecate Newsletter API Endpoints
- [x] 2.4.1 Deprecation header added (done in T0)
- [x] 2.4.2 Sunset header set to 2026-06-30 (D4 target)
- [x] 2.4.3 OpenAPI endpoints marked deprecated=True (done in T0)
- [x] 2.4.4 Warning logs on deprecated endpoint usage (done in T0)

### 2.5 Testing
- [x] 2.5.1 Ingestion flows verified - API routes use Content services
- [x] 2.5.2 Summarization works - content_id properly set, hack removed
- [x] 2.5.3 Digest creation verified in T0
- [x] 2.5.4 240 model/utility tests pass

---

## Phase 3: Frontend Removal ✅

**Dependencies**: Phase 2 must be complete and deployed
**Status**: Complete

### 3.1 Route Redirect
- [x] 3.1.1 Replace `newsletters.tsx` with redirect component to `/contents`
- [x] 3.1.2 Client-side redirect with `replace: true` (no back-button entry)
- [x] 3.1.3 Route definition kept to prevent 404s

### 3.2 Type Migration
- [x] 3.2.1 Create type aliases: `Newsletter = Content`, `NewsletterSource = ContentSource`
- [x] 3.2.2 Types are now aliases - components work with Content types
- [x] 3.2.3 Newsletter hooks marked deprecated (still available during transition)

### 3.3 Component Cleanup
- [x] 3.3.1 `IngestNewslettersDialog` marked deprecated (use `IngestContentsDialog`)
- [x] 3.3.2 `NewsletterPane` marked deprecated (use `ContentPane`)
- [x] 3.3.3 All Newsletter exports have @deprecated JSDoc comments

### 3.4 Testing
- [x] 3.4.1 `/newsletters` redirects to `/contents` (client-side)
- [x] 3.4.2 TypeScript passes with no errors
- [x] 3.4.3 Dev servers running, application functional

---

## Phase 4: Model Cleanup

**Dependencies**: Phase 3 complete + 2 weeks production verification with no Newsletter usage

### 4.1 Pre-Removal Verification
- [x] 4.1.1 Verify zero Newsletter API calls in logs for 2 weeks
  - Single-user project, owner verified no active Newsletter usage
- [x] 4.1.2 Verify zero Newsletter model queries in application logs
  - All new ingestion uses Content model exclusively
- [x] 4.1.3 Create backup of `newsletters` table data
  - Owner confirmed data can be re-ingested if needed; clean slate preferred

### 4.2 Backend Removal
- [x] 4.2.1 Remove `src/models/newsletter.py`
- [x] 4.2.2 Remove `src/api/newsletter_routes.py`
  - Already unregistered from router; file didn't exist
- [x] 4.2.3 Remove Newsletter from `src/models/__init__.py` exports
- [x] 4.2.4 Remove Newsletter from API router registration
  - Already done in previous work

### 4.3 Database Cleanup
- [x] 4.3.1 Create Alembic migration to drop `newsletter_id` FK from `newsletter_summaries`
  - Migration `8753a5a83a94_drop_newsletter_table_and_fk.py`
- [x] 4.3.2 Create Alembic migration to drop `newsletters` table
  - Same migration drops table with CASCADE
- [x] 4.3.3 Run migrations on staging, verify
  - Ran on local dev database, verified table removed
- [x] 4.3.4 Run migrations on production
  - Local is production for single-user project
- [x] 4.3.5 Rename `newsletter_summaries` table to `summaries`
  - Migration `b846f2b0247c_rename_newsletter_summaries_to_summaries.py`
  - Updated all indexes and FK constraints

### 4.4 Frontend Removal
- [x] 4.4.1 Delete `web/src/routes/newsletters.tsx`
- [x] 4.4.2 Delete `web/src/types/newsletter.ts`
- [x] 4.4.3 Delete Newsletter hooks from `web/src/hooks/`
  - Deleted `use-newsletters.ts`
  - Deleted `NewsletterPane.tsx` component
  - Updated exports in `hooks/index.ts`
- [x] 4.4.4 Remove Newsletter route from router configuration
  - `routeTree.gen.ts` auto-regenerated without Newsletter route

### 4.5 Final Cleanup
- [x] 4.5.1 Search codebase for any remaining "newsletter" references
  - Updated 37+ files with content terminology
  - Preserved backwards-compatible aliases (NewsletterSummary, NewsletterSummarizer)
- [x] 4.5.2 Update all documentation to remove Newsletter mentions
  - Updated ARCHITECTURE.md, DEVELOPMENT.md, MODEL_CONFIGURATION.md
  - Updated REVIEW_SYSTEM.md, MARKDOWN_PIPELINE_DESIGN.md
  - Added historical notes to CASE_STUDIES.md
- [x] 4.5.3 Update CLAUDE.md to remove Newsletter guidance
  - Removed "Newsletter model is deprecated" gotcha (it's gone, not deprecated)
- [x] 4.5.4 Archive this proposal
  - Moved to openspec/changes/archive/2026-01-24-deprecate-newsletter-model/

---

## ✅ PROPOSAL COMPLETE

All phases completed on 2026-01-24. The Newsletter model has been fully removed from the codebase.

---

## Rollback Plan

### Phase 1 Rollback
- Revert navigation changes
- Remove deprecation banner
- Remove deprecation comments

### Phase 2 Rollback
- Re-enable dual-write code paths
- Newsletter data still exists, no data loss

### Phase 3 Rollback
- Restore `newsletters.tsx` from git
- Remove redirects
- Restore type definitions

### Phase 4 Rollback
- **NOT EASILY REVERSIBLE** - requires database restore
- Ensure backup is verified before proceeding
- Consider keeping `newsletters` table for 30 days post-migration
