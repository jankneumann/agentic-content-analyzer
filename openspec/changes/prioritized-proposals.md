# Proposal Prioritization Report

**Date**: 2026-02-21 22:45:00
**Analyzed Range**: HEAD~50..HEAD (50 commits)
**Proposals Analyzed**: 14 active proposals

---

## Context: Recently Completed Work

The following proposals were **implemented and archived** since the last prioritization (2026-02-12):

| Archived Proposal | PR | Key Impact |
|---|---|---|
| `add-async-youtube-ingestion` | #171 | YouTube ingestion is now async/parallel |
| `add-api-contract-testing` | #201 | Schemathesis schema + fuzz testing |
| `add-hoverfly-api-simulation` | #200 | HTTP-level integration test infrastructure |
| `add-user-authentication` | #202 | Owner auth (middleware + session cookies + X-Admin-Key) |
| `add-embedding-provider-switching` | #184 | Multi-provider embeddings with safe switching |
| `add-settings-management` | #190 | Settings UI (models, voice, connections) |

Additionally, significant infrastructure work landed: queue worker rewrite (#199), security hardening (sentinel PRs #185, #188, #192, #203), search optimizations (#169, #177, #180, #187), and Neon branch management foundation (CLI, profiles, CI workflow).

---

## Priority Order

### 1. add-neon-branch-management — Verify & Complete

- **Relevance**: **Partially Implemented** — CLI commands, profiles (`ci-neon.yaml`, `railway-neon.yaml`), CI workflow (`neon-pr.yml`), and Makefile targets already merged
- **Readiness**: Partially Ready (0/22 tasks formally checked off, but ~60% of scope is done)
- **Conflicts**: None with other proposals
- **Remaining Work**:
  - Section 1: Skill integration in `agentic-coding-tools` repo
  - Section 2: Test infrastructure (pytest markers, session fixtures)
  - Section 4: CLI unit tests
  - Section 5: Documentation updates
- **Recommendation**: **Verify implemented work, update tasks.md, complete remaining sections**
- **Next Step**: `/validate-feature add-neon-branch-management` then continue implementation

### 2. add-crawl4ai-integration — Quick Win

- **Relevance**: Still Relevant — JS-heavy pages return incomplete content
- **Readiness**: Ready (0/28 tasks, no design.md needed — activates existing disabled code in `html_markdown_converter.py`)
- **Conflicts**: `docker-compose.yml` (additive), `pyproject.toml` (additive), `src/config/settings.py` (additive)
- **Scope**: Small — the parser fallback path is already coded but disabled
- **Recommendation**: **Implement next** — smallest scope, highest isolation, immediate user-facing value
- **Next Step**: `/implement-feature add-crawl4ai-integration`

### 3. content-sharing — Independent, High Value

- **Relevance**: Still Relevant — no content sharing mechanism exists
- **Readiness**: Ready (0/35 tasks, design doc complete)
- **Conflicts**: `src/models/content.py`, `src/models/summary.py` (additive columns), new route files
- **Scope**: Medium (models + migrations + API + templates + abuse controls)
- **Recommendation**: **Implement** — high user-facing value, fully independent
- **Next Step**: `/implement-feature content-sharing`

### 4. add-voice-input — Strategic Foundation (Unlocks 4 Proposals)

- **Relevance**: Still Relevant — no voice input exists. Settings UI has a `VoiceConfigurator` placeholder but no backend STT engine
- **Readiness**: Ready (0/58 tasks, design doc complete)
- **Conflicts**: `src/config/models.py`, `web/src/components/chat/ChatInput.tsx`, new API routes
- **Scope**: Large (58 tasks: Web Speech API, voice button, LLM cleanup endpoint)
- **Strategic Value**: **Unlocks 4 dependent proposals**: add-on-device-stt, add-cloud-stt, add-capacitor-mobile, add-tauri-desktop
- **Recommendation**: **Implement as strategic priority** — the voice stack funnel depends on this
- **Next Step**: `/implement-feature add-voice-input`

### 5. add-notification-events — Strategic Foundation (Unlocks 2 Proposals)

- **Relevance**: Still Relevant — no event notification system exists
- **Readiness**: Ready (0/54 tasks, design doc complete)
- **Conflicts**: New DB tables, new route files, `src/api/app.py` (SSE mount)
- **Scope**: Large (54 tasks: event types, dispatcher, SSE, device registration, frontend bell)
- **Strategic Value**: **Unlocks 2 dependent proposals**: add-capacitor-mobile, add-tauri-desktop
- **Recommendation**: **Implement** — independent of voice stack, parallel with #4
- **Next Step**: `/implement-feature add-notification-events`

### 6. add-grok-x-search — New Content Source

- **Relevance**: Still Relevant — no X/Twitter ingestion exists
- **Readiness**: Ready (0/34 tasks, design doc complete)
- **Conflicts**: `src/models/content.py` (ContentSource enum), `alembic/` (migration), `src/config/settings.py`
- **Scope**: Medium (follows established Client-Service ingestion pattern)
- **Recommendation**: Implement — isolated, follows existing patterns
- **Next Step**: `/implement-feature add-grok-x-search`

### 7. add-image-generator-service — Independent Feature

- **Relevance**: Still Relevant — AI image generation for digests/summaries
- **Readiness**: Ready (0/20 tasks, design doc complete)
- **Conflicts**: `src/config/settings.py` (additive), new route files
- **Scope**: Small (20 tasks, smallest remaining proposal)
- **Recommendation**: Implement — small, self-contained
- **Next Step**: `/implement-feature add-image-generator-service`

### 8. add-mobile-content-capture — Partially Implemented

- **Relevance**: **Needs Verification** — `src/api/save_routes.py` already exists with `POST /api/v1/content/save-url`, web save page, background extraction, and template system
- **Readiness**: Partially Ready (0/48 tasks formally, but ~40% of core API is done)
- **Conflicts**: Minimal — mostly new files (iOS Shortcut, API key auth module)
- **Remaining Work**: iOS Shortcut file, API key authentication system, rate limiting per key, integration tests
- **Recommendation**: **Verify existing implementation, update tasks.md, complete remaining**
- **Next Step**: `/validate-feature add-mobile-content-capture`

### 9. add-deployment-pipeline — Needs Refinement

- **Relevance**: **Needs Refinement** — CI exists (`ci.yml`), Dockerfile exists, Railway build workflow exists. CD (deploy.yml) does not. Tasks reference Redis (removed) and PG15 (now PG17)
- **Readiness**: Partially Ready — CI ~70% done, CD 0%, several tasks outdated
- **Conflicts**: `.github/workflows/`, `Dockerfile`, `docker-compose.yml`
- **Scope**: Large (49 tasks, but many already done or obsolete)
- **Recommendation**: **Rewrite tasks.md** — remove completed/obsolete tasks, focus on remaining CD pipeline
- **Next Step**: `/iterate-on-plan add-deployment-pipeline`

### 10. add-on-device-stt — Blocked

- **Relevance**: Still Relevant — privacy-focused offline STT via Whisper WASM
- **Readiness**: **Blocked** — depends on add-voice-input (#4) for `STTEngine` interface
- **Conflicts**: `web/src/lib/voice/` (extends voice-input files)
- **Recommendation**: Implement after add-voice-input completes
- **Next Step**: Wait for #4, then `/implement-feature add-on-device-stt`

### 11. add-cloud-stt — Blocked

- **Relevance**: Still Relevant — cloud streaming STT (Gemini, OpenAI, Deepgram)
- **Readiness**: **Blocked** — depends on add-voice-input (#4) for `STTEngine` interface
- **Conflicts**: `web/src/lib/voice/`, `src/api/voice_*`, `src/config/models.py`
- **Recommendation**: Implement after add-voice-input completes (can parallel with add-on-device-stt)
- **Next Step**: Wait for #4, then `/implement-feature add-cloud-stt`

### 12. add-capacitor-mobile — Blocked (2 dependencies)

- **Relevance**: Still Relevant — native iOS app via Capacitor
- **Readiness**: **Blocked** — depends on add-voice-input (#4) AND add-notification-events (#5)
- **Conflicts**: `web/src/lib/platform.ts`, Capacitor config, iOS-specific build
- **Recommendation**: Implement after both dependencies complete
- **Next Step**: Wait for #4 + #5, then `/implement-feature add-capacitor-mobile`

### 13. add-tauri-desktop — Blocked (2 dependencies)

- **Relevance**: Still Relevant — native desktop via Tauri (Rust)
- **Readiness**: **Blocked** — depends on add-voice-input (#4) AND add-notification-events (#5)
- **Conflicts**: `web/src/lib/platform.ts`, `src-tauri/` (new directory)
- **Recommendation**: Implement after both dependencies complete
- **Next Step**: Wait for #4 + #5, then `/implement-feature add-tauri-desktop`

### 14. add-api-versioning — Defer

- **Relevance**: Still Relevant but low urgency — single consumer, no breaking changes imminent
- **Readiness**: Ready (0/42 tasks, design doc complete)
- **Conflicts**: **CRITICAL** — restructures ALL route files in `src/api/`
- **Scope**: Large (42 tasks), highest blast radius of all proposals
- **Recommendation**: **Defer** — implement only when breaking API changes become necessary
- **Next Step**: Revisit after content-sharing and native platform features ship

---

## Parallel Workstreams

### Stream A — Start Immediately (zero file conflicts)
- **add-neon-branch-management** (#1): Verify + complete remaining sections
- **add-crawl4ai-integration** (#2): Quick win, activates existing code
- **content-sharing** (#3): New models/routes, no overlap with above

### Stream B — Strategic Foundation (independent of each other)
- **add-voice-input** (#4): Browser STT + LLM cleanup
- **add-notification-events** (#5): Event system + SSE

These two proposals can run **in parallel** — voice touches `web/src/lib/voice/` and chat components, while notifications touches `src/services/notification_service.py` and new DB tables. No file overlap.

### Stream C — After Stream A (independent of Stream B)
- **add-grok-x-search** (#6): New ingestion source
- **add-image-generator-service** (#7): New generation service

### Stream D — Verify & Refine
- **add-mobile-content-capture** (#8): Verify existing save_routes.py, complete iOS Shortcut
- **add-deployment-pipeline** (#9): Rewrite tasks.md, implement CD pipeline

### Sequential — After Stream B Completes
1. **add-on-device-stt** (#10) + **add-cloud-stt** (#11) — after add-voice-input
2. **add-capacitor-mobile** (#12) + **add-tauri-desktop** (#13) — after voice-input AND notification-events
3. **add-api-versioning** (#14) — defer until breaking changes needed

---

## Dependency Graph

```
                    ┌─────────────────────┐
                    │   add-voice-input   │
                    │      (#4)           │
                    └──────┬──────┬───────┘
                           │      │
              ┌────────────┘      └────────────┐
              ▼                                ▼
    ┌─────────────────┐              ┌──────────────────┐
    │ add-on-device-  │              │   add-cloud-stt  │
    │    stt (#10)    │              │      (#11)       │
    └─────────────────┘              └──────────────────┘
              │                                │
              └────────────┐      ┌────────────┘
                           ▼      ▼
                    ┌──────────────────────┐
                    │ add-capacitor-mobile │◄──┐
                    │       (#12)          │   │
                    └──────────────────────┘   │
                                               │
                    ┌──────────────────────┐   │
                    │add-notification-     │───┘
                    │  events (#5)         │───┐
                    └──────────────────────┘   │
                                               │
                    ┌──────────────────────┐   │
                    │  add-tauri-desktop   │◄──┘
                    │       (#13)          │
                    └──────────────────────┘
```

All other proposals (crawl4ai, content-sharing, grok-x-search, image-generator, neon-branch, mobile-content-capture, deployment-pipeline, api-versioning) are **independent** — no cross-proposal dependencies.

---

## Conflict Matrix

| | neon | crawl4ai | sharing | voice | notif | grok-x | img-gen | mobile | deploy | on-stt | cloud-stt | capacitor | tauri | api-ver |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **neon** | — | — | — | — | — | — | — | — | ci.yml | — | — | — | — | — |
| **crawl4ai** | — | — | — | — | — | settings, pyproject | settings | — | docker | — | — | — | — | — |
| **sharing** | — | — | — | — | — | content.py | — | — | — | — | — | — | — | **all routes** |
| **voice** | — | — | — | — | — | — | — | — | — | **voice/** | **voice/** | **voice/** | **voice/** | routes |
| **notif** | — | — | — | — | — | — | — | — | — | — | — | **events** | **events** | routes |
| **grok-x** | — | settings, pyproject | content.py | — | — | — | settings | — | — | — | — | — | — | routes |
| **img-gen** | — | settings | — | — | — | settings | — | — | — | — | — | — | — | routes |
| **mobile** | — | — | — | — | — | — | — | — | — | — | — | — | — | routes |
| **deploy** | ci.yml | docker | — | — | — | — | — | — | — | — | — | — | — | — |
| **on-stt** | — | — | — | **voice/** | — | — | — | — | — | — | — | — | — | — |
| **cloud-stt** | — | — | — | **voice/** | — | — | — | — | — | — | — | — | — | — |
| **capacitor** | — | — | — | **voice/** | **events** | — | — | — | — | — | — | — | platform.ts | — |
| **tauri** | — | — | — | **voice/** | **events** | — | — | — | — | — | — | platform.ts | — | — |
| **api-ver** | — | — | **all routes** | routes | routes | routes | routes | routes | — | — | — | — | — | — |

**Legend**: Bold = high conflict (core shared files), regular = minor overlap (additive config changes)

---

## Proposals Needing Attention

### Partially Implemented (verify before continuing)
- **add-neon-branch-management**: CLI, profiles, CI workflow landed — verify and complete remaining skill/test/doc sections
- **add-mobile-content-capture**: `save_routes.py` with save-url endpoint exists — verify scope, complete iOS Shortcut and API key auth

### Needs Refinement
- **add-deployment-pipeline**: Tasks reference Redis (removed) and PG15 (now PG17). CI already exists. Rewrite tasks to focus on remaining CD pipeline.

### Blocked (waiting on dependencies)
- **add-on-device-stt**: Waiting on add-voice-input
- **add-cloud-stt**: Waiting on add-voice-input
- **add-capacitor-mobile**: Waiting on add-voice-input + add-notification-events
- **add-tauri-desktop**: Waiting on add-voice-input + add-notification-events

### Deferred
- **add-api-versioning**: High blast radius, low urgency — defer until breaking changes needed
