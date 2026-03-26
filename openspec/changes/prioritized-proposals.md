# Proposal Prioritization Report

**Date**: 2026-03-26 09:30:00
**Analyzed Range**: HEAD~50..HEAD (50 commits)
**Proposals Analyzed**: 8 active proposals (1 fully implemented, 7 remaining)

---

## Context: Recently Completed Work

Since the last prioritization (2026-02-21), the following features were **implemented and merged**:

| Feature | PR/Status | Key Impact |
|---------|-----------|------------|
| `add-blog-scraping` | #318 | Blog index scraping, CSS selector + heuristic link discovery |
| `add-digest-followup-prompts` | #296, #316 | Per-section follow-up prompts in digests |
| `add-deployment-pipeline` | #306 | Railway deployment + ParadeDB migration |
| `cli-thin-http-client` | Multiple PRs | CLI refactored as thin HTTP client |
| `harden-public-repo-security` | #313 | Security hardening for public visibility |
| `provider-agnostic-pipeline` | #291 | All pipeline LLM calls through LLMRouter |
| `persist-theme-analysis` | #282 | Theme analysis persistence + history UI |

**Additionally implemented** (previously, without formal OpenSpec archiving):
- `add-voice-input` — Browser STT + voice UI (unblocks on-device-stt, capacitor, tauri)
- `add-notification-events` — Event notification system (unblocks capacitor, tauri)
- `content-sharing` — Share tokens, share routes, public links
- `add-neon-branch-management` — CLI commands, profiles, CI workflow
- `add-grok-x-search` — X/Twitter ingestion via xAI Grok API
- `add-perplexity-search` — Perplexity Sonar API search
- `add-user-authentication` — AuthMiddleware, session cookies, X-Admin-Key
- `add-image-generator-service` — Image generation service (partial)
- `content-capture` / `save-url` — Save URL API endpoint exists

**Impact on blockers**: 4 proposals that were "Blocked" in the Feb 21 report are **now unblocked**.

---

## Priority Order

### 1. add-blog-scraping — Archive (Fully Implemented)

- **Relevance**: **Fully Implemented** — merged as PR #318, all 9 tasks done
- **Readiness**: Complete
- **Conflicts**: None
- **Recommendation**: **Archive immediately** — proposal still in `openspec/changes/` but code is on main
- **Next Step**: `openspec archive add-blog-scraping --yes`

### 2. add-crawl4ai-integration — Quick Win, Activates Existing Code

- **Relevance**: **Still Relevant** — JS-heavy pages return incomplete content. Crawl4AI fallback code exists in `HtmlMarkdownConverter` but is disabled.
- **Readiness**: Ready (0/28 tasks, no design.md needed — activates existing code)
- **Conflicts**: `docker-compose.yml` (additive), `pyproject.toml` (additive), `src/config/settings.py` (additive)
- **Scope**: Small-Medium — existing code path needs activation, Docker service, configuration
- **Recommendation**: **Implement next** — smallest actionable scope, immediate user-facing value, enhances blog scraping quality
- **Next Step**: `/implement-feature add-crawl4ai-integration`

### 3. add-kreuzberg-optional-parser — Independent, Medium Scope

- **Relevance**: **Still Relevant** — adds quality comparison and format coverage alongside MarkItDown/Docling
- **Readiness**: Ready (0/19 tasks, no design.md — but proposal has detailed design in proposal.md)
- **Conflicts**: `src/parsers/` — **overlaps with crawl4ai** on parser layer, `src/config/settings.py` (additive)
- **Scope**: Medium (6 phases: dependency, adapter, router, shadow evaluation, tests, rollout)
- **Recommendation**: **Implement after crawl4ai** — both touch parser router, serialized execution avoids conflicts
- **Next Step**: `/implement-feature add-kreuzberg-optional-parser`

### 4. add-mobile-content-capture — Partially Implemented, Verify & Complete

- **Relevance**: **Partially Implemented** — `src/api/save_routes.py` exists with `POST /api/v1/content/save-url`, web save page, background extraction
- **Readiness**: Partially Ready (0/48 tasks formally, but ~40% of core API exists)
- **Conflicts**: Minimal — mostly new files (iOS Shortcut, API key auth)
- **Remaining Work**: iOS Shortcut file, API key authentication, rate limiting, integration tests, mobile save page polish
- **Recommendation**: **Verify existing implementation, update tasks.md, complete remaining work**
- **Next Step**: `/validate-feature add-mobile-content-capture` then continue implementation

### 5. add-on-device-stt — NOW UNBLOCKED, Strategic

- **Relevance**: **Still Relevant** — privacy-focused offline STT via Whisper WASM
- **Readiness**: **Now Unblocked** — `add-voice-input` is implemented (STTEngine interface exists)
- **Conflicts**: `web/src/lib/voice/` (extends voice-input files) — potential overlap with capacitor/tauri
- **Scope**: Large (39 tasks: STT abstraction, Whisper WASM, model management, audio recording, settings, UI)
- **Recommendation**: **Implement** — strategic foundation for native STT in Capacitor/Tauri
- **Next Step**: `/implement-feature add-on-device-stt`

### 6. add-capacitor-mobile — NOW UNBLOCKED, High User Value

- **Relevance**: **Still Relevant** — native iOS app for content reading
- **Readiness**: **Now Unblocked** — both `add-voice-input` and `add-notification-events` are implemented
- **Conflicts**: `web/src/lib/platform.ts` (shared with Tauri), Capacitor config, iOS build
- **Scope**: Large (50 tasks: setup, platform detection, plugins, push, share target, STT, build, deploy)
- **Recommendation**: **Implement before Tauri** — higher user value (mobile-first content reading)
- **Next Step**: `/implement-feature add-capacitor-mobile`

### 7. add-tauri-desktop — NOW UNBLOCKED, After Capacitor

- **Relevance**: **Still Relevant** — native desktop via Rust/Tauri
- **Readiness**: **Now Unblocked** — both dependencies implemented
- **Conflicts**: `web/src/lib/platform.ts` (shared with Capacitor) — **must serialize with Capacitor**
- **Scope**: Large (41 tasks: setup, platform detection, system tray, shortcuts, drag-drop, notifications)
- **Recommendation**: **Implement after Capacitor** — Capacitor establishes platform.ts abstractions
- **Next Step**: Wait for Capacitor, then `/implement-feature add-tauri-desktop`

### 8. add-api-versioning — Defer

- **Relevance**: Still Relevant but low urgency — single consumer, no breaking changes imminent
- **Readiness**: Ready (0/42 tasks, design doc complete)
- **Conflicts**: **CRITICAL** — restructures ALL route files in `src/api/`
- **Scope**: Large (42 tasks), highest blast radius of all proposals
- **Recommendation**: **Defer** — implement only when breaking API changes become necessary
- **Next Step**: Revisit after native platform features ship

---

## Parallel Workstreams

### Stream A — Start Immediately (zero file conflicts)
- **add-crawl4ai-integration** (#2): Quick win, activates existing code in parser layer
- **add-mobile-content-capture** (#4): Verify existing save_routes.py, complete iOS Shortcut — touches API routes, no parser overlap

### Stream B — After Crawl4AI completes (parser layer overlap)
- **add-kreuzberg-optional-parser** (#3): Both touch `src/parsers/` router, serialize with crawl4ai

### Stream C — Platform Features (independent of Streams A+B)
- **add-on-device-stt** (#5): Frontend voice layer (`web/src/lib/voice/`)
- Can run in parallel with Streams A+B — different layers entirely

### Stream D — Native Platforms (after Stream C, serialize with each other)
1. **add-capacitor-mobile** (#6): First — establishes `platform.ts` abstraction
2. **add-tauri-desktop** (#7): Second — builds on platform abstraction

### Deferred
- **add-api-versioning** (#8): Defer until breaking changes needed

### Housekeeping
- **add-blog-scraping** (#1): Archive immediately (fully implemented)

---

## Dependency Graph (Updated)

```
  ✅ = Implemented     ⬜ = Active proposal

          ✅ add-voice-input
                │
       ┌────────┴─────────┐
       ▼                   ▼
  ⬜ add-on-device-    ✅ add-cloud-stt
       stt (#5)            (implicit)
       │                   │
       └────────┬──────────┘
                ▼
  ✅ add-notification-events
                │
       ┌────────┴─────────┐
       ▼                   ▼
  ⬜ add-capacitor-    ⬜ add-tauri-
     mobile (#6)         desktop (#7)

  --- Independent ---

  ⬜ add-crawl4ai (#2) ──→ ⬜ add-kreuzberg (#3)
                                (parser layer overlap)

  ⬜ add-mobile-capture (#4)    (independent)

  ⬜ add-api-versioning (#8)    (deferred, global blast radius)
```

---

## Conflict Matrix

| | crawl4ai | kreuzberg | mobile-cap | on-stt | capacitor | tauri | api-ver |
|---|---|---|---|---|---|---|---|
| **crawl4ai** | — | **parsers/, settings** | — | — | — | — | — |
| **kreuzberg** | **parsers/, settings** | — | — | — | — | — | — |
| **mobile-cap** | — | — | — | — | — | — | routes |
| **on-stt** | — | — | — | — | voice/ | voice/ | — |
| **capacitor** | — | — | — | voice/ | — | **platform.ts** | — |
| **tauri** | — | — | — | voice/ | **platform.ts** | — | — |
| **api-ver** | — | — | routes | — | — | — | — |

**Legend**: Bold = serialization required, regular = minor/additive overlap

---

## Proposals Needing Attention

### Fully Implemented (archive immediately)
- **add-blog-scraping**: PR #318 merged, all tasks done. Run `openspec archive add-blog-scraping --yes`

### Partially Implemented (verify before continuing)
- **add-mobile-content-capture**: `save_routes.py` exists with save-url endpoint — verify scope, update tasks.md, complete iOS Shortcut and API key auth

### Previously Blocked → Now Unblocked
- **add-on-device-stt**: `add-voice-input` is implemented — can proceed
- **add-capacitor-mobile**: Both `add-voice-input` and `add-notification-events` implemented — can proceed
- **add-tauri-desktop**: Both dependencies implemented — can proceed (after Capacitor)

### Deferred
- **add-api-versioning**: High blast radius, low urgency — defer until breaking changes needed
