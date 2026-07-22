# Tasks: Redesign YouTube Ingestion Pipeline

**Change ID**: `redesign-youtube-ingestion-pipeline`

## Parallelizability Notes

Phase 1 (config + model registry) is foundational. Phase 2 (router) and the
duration-probe parts of Phase 3 can proceed in parallel after Phase 1. The
router (3a/3b) depends on Phase 2. Tests (Phase 4) follow their targets.
Max parallel width: ~3.

---

## Phase 1: Config & model registry

- [x] 1.1 Add length-filter + routing fields to source models
  **Spec scenarios**: yt-route.1, yt-route.9
  **Files**: `src/config/sources.py` (modified)
  **Fields**: `min_duration_seconds`, `max_duration_seconds`,
  `long_video_threshold_seconds` (2700), `long_video_strategy` (`grounding`),
  `video_fps` (0.1), `segment_overlap_seconds` (15), `unknown_duration_strategy` (`short`)
  **Dependencies**: none

- [x] 1.2 Surface new fields in `sources.d/_defaults.yaml`, `youtube_rss.yaml`, `youtube_playlist.yaml`
  **Spec scenarios**: yt-route.9
  **Files**: `sources.d/*.yaml` (modified)
  **Dependencies**: 1.1

- [x] 1.3 Register short-video model + `youtube_long_processing` step
  **Spec scenarios**: yt-route.10
  **Files**: `settings/models.yaml`, `src/config/models.py` (ModelStep enum)
  **Note**: `gemini-3.1-flash-lite` is NOT in the registry — add entry or alias; confirm with user.
  **Dependencies**: none

## Phase 2: LLM router

- [x] 2.1 Extend `_generate_gemini_with_video` with `fps`/`start_offset`/`end_offset` via `types.VideoMetadata`
  **Spec scenarios**: yt-route.5, yt-route.8
  **Files**: `src/services/llm_router.py` (modified)
  **Note**: confirm `VideoMetadata` field names against installed `google-genai` (source-driven-development).
  **Dependencies**: none

- [x] 2.2 Add public `generate_with_grounding()` wrapping `_generate_gemini_with_tools`
  **Spec scenarios**: yt-route.7
  **Files**: `src/services/llm_router.py` (modified)
  **Dependencies**: none

## Phase 3: Ingestion routing

- [x] 3.1 Duration probing (Data API contentDetails + yt-dlp fallback + ISO-8601 parse)
  **Spec scenarios**: yt-route.3, yt-route.4
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 1.1

- [x] 3.2 Length + topic filter gate before processing
  **Spec scenarios**: yt-route.1, yt-route.2
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 3.1

- [x] 3.3 Duration router replacing the fallback chain in `_process_video`
  **Spec scenarios**: yt-route.5, yt-route.6
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 2.1, 3.2

- [x] 3.4 New timestamped-segment extraction prompt for the short path
  **Spec scenarios**: yt-route.5
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 3.3

- [x] 3.5 Long-video grounding branch (default)
  **Spec scenarios**: yt-route.7
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 2.2, 3.3

- [x] 3.6 Long-video segments branch (opt-in): window split + per-window call + stitch/de-dup
  **Spec scenarios**: yt-route.8
  **Files**: `src/ingestion/youtube.py` (modified)
  **Dependencies**: 2.1, 3.3

## Phase 4: Tests & docs

- [x] 4.1 Router unit tests (fps/offsets passthrough, grounding delegation)
  **Spec scenarios**: yt-route.5, yt-route.7, yt-route.8
  **Files**: `tests/.../test_llm_router_video.py` (new)
  **Dependencies**: 2.1, 2.2

- [x] 4.2 Router/duration tests (boundary, filters, unknown duration)
  **Spec scenarios**: yt-route.1, yt-route.2, yt-route.4, yt-route.6
  **Files**: `tests/.../test_youtube_router.py` (new)
  **Dependencies**: 3.3

- [x] 4.3 Segmentation tests (window math + stitch de-dup)
  **Spec scenarios**: yt-route.8
  **Files**: `tests/.../test_youtube_segments.py` (new)
  **Dependencies**: 3.6

- [x] 4.4 Config round-trip tests + docs update (ARCHITECTURE.md, SETUP.md source fields)
  **Spec scenarios**: yt-route.9, yt-route.10
  **Files**: `tests/.../test_sources_config.py`, `docs/ARCHITECTURE.md`, `docs/SETUP.md`
  **Dependencies**: 1.1, 1.2, 1.3
