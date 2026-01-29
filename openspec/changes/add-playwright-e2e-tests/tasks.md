## 1. Test Infrastructure
- [x] 1.1 Create `fixtures/mock-data.ts` — typed factory functions for all API response types
- [x] 1.2 Create `fixtures/api-mocks.ts` — ApiMocks class with route interception for all endpoints
- [x] 1.3 Create `fixtures/base.page.ts` — BasePage with shared layout locators (sidebar, header, breadcrumbs)
- [x] 1.4 Create `fixtures/index.ts` — custom `test` export extending base with page object fixtures
- [x] 1.5 Create page objects: dashboard, contents, summaries, digests, scripts, podcasts, audio-digests, themes, review, settings

## 2. Configuration Updates
- [x] 2.1 Update `web/playwright.config.ts` — add actionTimeout, video on CI, global timeout, expect.timeout, smoke project
- [x] 2.2 Install `@axe-core/playwright` devDependency
- [x] 2.3 Add test:e2e scripts to package.json (if needed)

## 3. Layout & Navigation Tests
- [x] 3.1 Create `layout/navigation.spec.ts` — sidebar links, active state, breadcrumbs, collapse toggle
- [x] 3.2 Create `layout/responsive.spec.ts` — mobile sidebar, hamburger menu, backdrop dismiss, safe area
- [x] 3.3 Create `layout/theme-toggle.spec.ts` — dark/light toggle, localStorage persistence, icon swap

## 4. Dashboard Tests
- [x] 4.1 Create `dashboard/dashboard.spec.ts` — pipeline status cards, quick actions, stats display

## 5. Content Tests
- [x] 5.1 Create `contents/contents-list.spec.ts` — table rendering, search, filters, sort, pagination
- [x] 5.2 Create `contents/contents-detail.spec.ts` — dialog opens, markdown content, metadata
- [x] 5.3 Create `contents/contents-ingest.spec.ts` — source tabs, max_results, submit

## 6. Summary Tests
- [x] 6.1 Create `summaries/summaries-list.spec.ts` — table, search, model filter, sort
- [x] 6.2 Create `summaries/summaries-detail.spec.ts` — executive summary, themes, insights
- [x] 6.3 Create `summaries/summaries-generate.spec.ts` — model selection, batch size, submit

## 7. Digest Tests
- [x] 7.1 Create `digests/digests-list.spec.ts` — table, search, type/status filters, sort
- [x] 7.2 Create `digests/digests-detail.spec.ts` — tabs, sources, approve/reject
- [x] 7.3 Create `digests/digests-generate.spec.ts` — daily/weekly tabs, date range, submit
- [x] 7.4 Create `digests/digests-review.spec.ts` — review queue integration

## 8. Script Tests
- [x] 8.1 Create `scripts/scripts-list.spec.ts` — table, status filter, sort
- [x] 8.2 Create `scripts/scripts-detail.spec.ts` — dialogue sections, speaker badges
- [x] 8.3 Create `scripts/scripts-generate.spec.ts` — digest selection, length tabs
- [x] 8.4 Create `scripts/scripts-review.spec.ts` — review workflow

## 9. Podcast Tests
- [x] 9.1 Create `podcasts/podcasts-list.spec.ts` — table, status filter, sort
- [x] 9.2 Create `podcasts/podcasts-player.spec.ts` — audio player controls
- [x] 9.3 Create `podcasts/podcasts-generate.spec.ts` — script selection, voice provider

## 10. Audio Digest Tests
- [x] 10.1 Create `audio-digests/audio-digests-list.spec.ts` — table, status filter, delete confirmation
- [x] 10.2 Create `audio-digests/audio-digests-player.spec.ts` — audio player controls
- [x] 10.3 Create `audio-digests/audio-digests-generate.spec.ts` — digest selection, voice/speed

## 11. Theme Tests
- [x] 11.1 Create `themes/themes-analysis.spec.ts` — stats cards, theme list, analyze trigger

## 12. Review System Tests
- [x] 12.1 Create `review/review-queue.spec.ts` — index page, pending items, navigation
- [x] 12.2 Create `review/digest-review.spec.ts` — two-pane layout, chat panel
- [x] 12.3 Create `review/summary-review.spec.ts` — content/summary panes
- [x] 12.4 Create `review/script-review.spec.ts` — digest/script panes

## 13. Cross-Cutting Tests
- [x] 13.1 Create `cross-cutting/empty-states.spec.ts` — all pages with empty data
- [x] 13.2 Create `cross-cutting/error-states.spec.ts` — API 500 errors, retry buttons
- [x] 13.3 Create `cross-cutting/loading-states.spec.ts` — skeleton loaders during delay
- [x] 13.4 Create `cross-cutting/background-tasks.spec.ts` — indicator, progress, completion
- [x] 13.5 Create `cross-cutting/accessibility.spec.ts` — axe-core WCAG 2.0 AA on every page

## 14. Smoke Tests
- [x] 14.1 Create `smoke/smoke.spec.ts` — real backend integration tests tagged @smoke

## 15. Documentation
- [x] 15.1 Update CLAUDE.md with E2E test commands and gotchas
