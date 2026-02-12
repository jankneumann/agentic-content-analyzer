# Proposal Prioritization Report

**Date**: 2026-02-12 18:30:00
**Analyzed Range**: HEAD~50..HEAD (50 commits)
**Proposals Analyzed**: 15 active directories (4 already implemented, 11 still relevant)

---

## Housekeeping: Proposals to Archive

These proposals are **fully implemented** but their directories were never cleaned up. Archive before starting new work to reduce confusion.

| Proposal | Implemented In | Action |
|----------|---------------|--------|
| `add-document-search` | PR #162, already archived at `archive/2026-02-12-add-document-search/` | Delete stale active dir (duplicate of archive) |
| `add-advanced-document-search` | Merged into `add-document-search`, all tasks `[x]` | `openspec archive add-advanced-document-search` |
| `add-hybrid-search-rrf` | Merged into `add-document-search`, all tasks `[x]` | `openspec archive add-hybrid-search-rrf` |
| `add-substack-api-ingest` | All 5 tasks `[x]`, CLI commands operational | `openspec archive add-substack-api-ingest` |

---

## Priority Order

### 1. add-async-youtube-ingestion

- **Relevance**: Still Relevant -- YouTube ingestion is sequential; 50 videos = ~25 min
- **Readiness**: Ready (0/45 tasks, design doc complete, clear scope)
- **Conflicts**: Minimal -- only `src/config/settings.py` (additive fields)
- **Scope**: Medium (mostly `src/ingestion/youtube.py` async refactor)
- **Recommendation**: **Implement next** -- isolated scope, high user-facing value (25 min to ~5 min), no blockers
- **Next Step**: `/implement-feature add-async-youtube-ingestion`

### 2. add-grok-x-search

- **Relevance**: Still Relevant -- no X/Twitter ingestion source exists
- **Readiness**: Ready (0/34 tasks, design doc complete)
- **Conflicts**: `src/models/content.py` (ContentSource enum), `src/config/settings.py`
- **Scope**: Medium (new ingestion source following established Client-Service pattern)
- **Recommendation**: Implement -- follows existing patterns, adds valuable new content source
- **Next Step**: `/implement-feature add-grok-x-search`

### 3. add-crawl4ai-integration

- **Relevance**: Still Relevant -- JS-heavy pages return incomplete content
- **Readiness**: Partially Ready (0/28 tasks, **no design.md**)
- **Conflicts**: `src/config/settings.py`, `pyproject.toml`, `docker-compose.yml`
- **Scope**: Small-Medium (activates existing disabled Crawl4AI fallback path)
- **Recommendation**: Create design.md first, then implement
- **Next Step**: `/iterate-on-plan add-crawl4ai-integration`

### 4. add-mobile-content-capture

- **Relevance**: Still Relevant -- iOS users have no Share Sheet integration
- **Readiness**: Ready (0/48 tasks, design doc complete)
- **Conflicts**: Minimal -- mostly new files (save_routes.py enhancement, templates, iOS Shortcut)
- **Scope**: Medium (API + mobile page + iOS Shortcut)
- **Recommendation**: Implement -- independent of other proposals, delivers mobile UX
- **Next Step**: `/implement-feature add-mobile-content-capture`

### 5. add-deployment-pipeline

- **Relevance**: Needs Verification -- CI (`ci.yml`) exists; CD (`deploy.yml`) does not
- **Readiness**: Partially Ready (CI ~70% done, CD 0% done, tasks not updated)
- **Conflicts**: `.github/workflows/`, `Dockerfile`, `docker-compose.yml`
- **Scope**: Large (49 tasks spanning Docker, CI, CD, environments)
- **Recommendation**: Update proposal to reflect current CI state, then implement remaining CD
- **Next Step**: `/iterate-on-plan add-deployment-pipeline`

### 6. add-image-generator-service

- **Relevance**: Still Relevant -- AI_GENERATED image type exists but no generation service
- **Readiness**: Ready (0/20 tasks, design doc complete)
- **Conflicts**: `src/config/settings.py`, new API routes
- **Scope**: Medium (new service + API endpoints + review integration)
- **Recommendation**: Implement -- small, self-contained feature
- **Next Step**: `/implement-feature add-image-generator-service`

### 7. content-sharing

- **Relevance**: Still Relevant -- no sharing mechanism exists
- **Readiness**: Ready (0/35 tasks, design doc complete)
- **Conflicts**: `src/models/content.py`, `src/models/summary.py`, existing route files -- overlaps with api-versioning
- **Scope**: Medium-Large (models + API + templates + migrations)
- **Recommendation**: Implement -- can proceed independently unless api-versioning is imminent
- **Next Step**: `/implement-feature content-sharing`

### 8. add-api-versioning

- **Relevance**: Still Relevant but low urgency (single consumer, no breaking changes imminent)
- **Readiness**: Ready (0/42 tasks, design doc complete)
- **Conflicts**: **CRITICAL** -- touches ALL route files in `src/api/`, reorganizes entire API layer
- **Scope**: Large (42 tasks)
- **Recommendation**: **Defer** -- high blast radius, low urgency for single-user app
- **Next Step**: Revisit when breaking API changes are needed

### 9. add-api-contract-testing

- **Relevance**: Still Relevant -- no automated contract validation
- **Readiness**: Ready (0/6 tasks, design doc complete)
- **Conflicts**: `.github/workflows/ci.yml`, `pyproject.toml`
- **Scope**: Small (6 tasks, mostly test tooling)
- **Recommendation**: Implement after deployment-pipeline stabilizes CI
- **Next Step**: `/implement-feature add-api-contract-testing` (after #5)

### 10. add-hoverfly-api-simulation

- **Relevance**: Still Relevant -- integration tests use direct mocks
- **Readiness**: Ready (0/4 tasks, design doc complete, smallest proposal)
- **Conflicts**: `docker-compose.yml`, `src/config/settings.py`
- **Scope**: Small (4 tasks)
- **Recommendation**: Implement as part of test infrastructure improvements
- **Next Step**: `/implement-feature add-hoverfly-api-simulation`

### 11. add-user-authentication

- **Relevance**: Still Relevant -- no user auth exists
- **Readiness**: **Blocked** -- proposal is DRAFT, references Node.js/Express (wrong stack), no design.md, needs security review
- **Conflicts**: **CRITICAL** -- touches ALL API routes, adds middleware to every endpoint
- **Scope**: Very Large (111 tasks, most complex proposal)
- **Recommendation**: **Needs complete rewrite** -- align with Python/FastAPI, add design doc, security review
- **Next Step**: Rewrite proposal from scratch with correct tech stack

---

## Parallel Workstreams

### Stream A (start immediately -- zero conflicts between these)
- **add-async-youtube-ingestion** (#1): `src/ingestion/youtube.py` (isolated)
- **add-mobile-content-capture** (#4): new files, `src/api/save_routes.py` (isolated)

### Stream B (start after Stream A, or in parallel if careful about settings.py)
- **add-grok-x-search** (#2): new ingestion source (mostly new files)
- **add-image-generator-service** (#6): new service (mostly new files)

### Stream C (infrastructure -- independent track)
- **add-deployment-pipeline** (#5): CI/CD workflows (after proposal update)
- **add-api-contract-testing** (#9): test tooling (after deployment-pipeline)
- **add-hoverfly-api-simulation** (#10): test tooling (independent)

### Sequential (high blast radius -- defer)
- **add-api-versioning** (#8): Wait until breaking API changes needed
- **content-sharing** (#7): Can proceed independently, benefits from versioning decision
- **add-user-authentication** (#11): Blocked until proposal rewrite

---

## Conflict Matrix

|  | async-yt | grok-x | crawl4ai | mobile | deploy | image-gen | sharing | api-ver | contract | hoverfly | user-auth |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **async-yt** | -- | settings | settings | none | none | settings | none | none | none | none | none |
| **grok-x** | settings | -- | settings, pyproject | none | none | settings, content.py | content.py | routes | none | settings | routes |
| **crawl4ai** | settings | settings, pyproject | -- | none | docker | settings | none | none | pyproject | docker | none |
| **mobile** | none | none | none | -- | none | none | none | routes | none | none | routes |
| **deploy** | none | none | docker | none | -- | none | none | none | ci.yml | docker | none |
| **image-gen** | settings | settings, content.py | settings | none | none | -- | none | routes | none | none | routes |
| **sharing** | none | content.py | none | none | none | none | -- | **all routes** | none | none | **all routes** |
| **api-ver** | none | routes | none | routes | none | routes | **all routes** | -- | none | none | **all routes** |
| **contract** | none | none | pyproject | none | ci.yml | none | none | none | -- | none | none |
| **hoverfly** | none | settings | docker | none | docker | none | none | none | none | -- | none |
| **user-auth** | none | routes | none | routes | none | routes | **all routes** | **all routes** | none | none | -- |

**Legend**: Bold = high conflict (same core files modified), regular = minor overlap (shared config files with additive changes)

---

## Proposals Needing Attention

### Likely Addressed (archive these)
- **add-document-search**: Fully implemented in PR #162, archived -- stale active dir is a duplicate
- **add-advanced-document-search**: Merged into add-document-search, all tasks complete
- **add-hybrid-search-rrf**: Merged into add-document-search, all tasks complete
- **add-substack-api-ingest**: All tasks complete, CLI commands operational

### Needs Refinement
- **add-deployment-pipeline**: CI partially exists (`ci.yml`), tasks don't reflect current state
- **add-crawl4ai-integration**: Missing design.md

### Blocked / Needs Rewrite
- **add-user-authentication**: DRAFT status, wrong tech stack (Node.js references), no design.md, no security review
