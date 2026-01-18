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

## Phase 2: Backend Migration

**Dependencies**: T0-REFactor-ContentModel must be complete (tasks 10.1-10.4)

### 2.1 Remove Dual-Write Code
- [ ] 2.1.1 Identify all dual-write locations (grep for Newsletter + Content writes)
- [ ] 2.1.2 Remove Newsletter writes from Gmail ingestion
- [ ] 2.1.3 Remove Newsletter writes from RSS ingestion
- [ ] 2.1.4 Remove Newsletter writes from YouTube ingestion
- [ ] 2.1.5 Update file upload to write only to Content

### 2.2 Update Foreign Key References
- [ ] 2.2.1 Create Alembic migration: add `content_id` to `newsletter_summaries` if not exists
- [ ] 2.2.2 Create data migration: populate `content_id` from `newsletter_id` mappings
- [ ] 2.2.3 Update `NewsletterSummary` model to use `content_id` as primary FK
- [ ] 2.2.4 Add backwards-compatible property for `newsletter_id` access

### 2.3 Update Processors
- [ ] 2.3.1 Update `summarizer.py` to query Content instead of Newsletter
- [ ] 2.3.2 Update `digest_creator.py` to use Content relationships
- [ ] 2.3.3 Update `theme_analyzer.py` if it references Newsletter
- [ ] 2.3.4 Update historical context queries

### 2.4 Deprecate Newsletter API Endpoints
- [ ] 2.4.1 Add `Deprecation` header to all `/api/v1/newsletters/*` responses
- [ ] 2.4.2 Add `Sunset` header with removal date (Phase 4 target)
- [ ] 2.4.3 Update OpenAPI docs to mark endpoints as deprecated
- [ ] 2.4.4 Log all Newsletter endpoint usage for monitoring

### 2.5 Testing
- [ ] 2.5.1 Verify all ingestion flows work without Newsletter writes
- [ ] 2.5.2 Verify summarization works with Content-only queries
- [ ] 2.5.3 Verify digest creation works with Content relationships
- [ ] 2.5.4 Run full regression test suite

---

## Phase 3: Frontend Removal

**Dependencies**: Phase 2 must be complete and deployed

### 3.1 Route Redirect
- [ ] 3.1.1 Replace `newsletters.tsx` content with redirect to `/contents`
- [ ] 3.1.2 Add HTTP 301 redirect header for SEO
- [ ] 3.1.3 Keep route definition to prevent 404s

### 3.2 Type Migration
- [ ] 3.2.1 Create type aliases: `Newsletter = Content`, `NewsletterSource = ContentSource`
- [ ] 3.2.2 Update all components using Newsletter types to use Content types
- [ ] 3.2.3 Remove Newsletter-specific hooks, replace with Content hooks

### 3.3 Component Cleanup
- [ ] 3.3.1 Remove `IngestNewslettersDialog` (use `IngestContentsDialog`)
- [ ] 3.3.2 Remove Newsletter-specific components
- [ ] 3.3.3 Update any shared components that had Newsletter variants

### 3.4 Testing
- [ ] 3.4.1 Verify `/newsletters` redirects properly
- [ ] 3.4.2 Verify no TypeScript errors after type migration
- [ ] 3.4.3 Manual QA of all Content-related flows

---

## Phase 4: Model Cleanup

**Dependencies**: Phase 3 complete + 2 weeks production verification with no Newsletter usage

### 4.1 Pre-Removal Verification
- [ ] 4.1.1 Verify zero Newsletter API calls in logs for 2 weeks
- [ ] 4.1.2 Verify zero Newsletter model queries in application logs
- [ ] 4.1.3 Create backup of `newsletters` table data

### 4.2 Backend Removal
- [ ] 4.2.1 Remove `src/models/newsletter.py`
- [ ] 4.2.2 Remove `src/api/newsletter_routes.py`
- [ ] 4.2.3 Remove Newsletter from `src/models/__init__.py` exports
- [ ] 4.2.4 Remove Newsletter from API router registration

### 4.3 Database Cleanup
- [ ] 4.3.1 Create Alembic migration to drop `newsletter_id` FK from `newsletter_summaries`
- [ ] 4.3.2 Create Alembic migration to drop `newsletters` table
- [ ] 4.3.3 Run migrations on staging, verify
- [ ] 4.3.4 Run migrations on production

### 4.4 Frontend Removal
- [ ] 4.4.1 Delete `web/src/routes/newsletters.tsx`
- [ ] 4.4.2 Delete `web/src/types/newsletter.ts`
- [ ] 4.4.3 Delete Newsletter hooks from `web/src/hooks/`
- [ ] 4.4.4 Remove Newsletter route from router configuration

### 4.5 Final Cleanup
- [ ] 4.5.1 Search codebase for any remaining "newsletter" references
- [ ] 4.5.2 Update all documentation to remove Newsletter mentions
- [ ] 4.5.3 Update CLAUDE.md to remove Newsletter guidance
- [ ] 4.5.4 Archive this proposal

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
