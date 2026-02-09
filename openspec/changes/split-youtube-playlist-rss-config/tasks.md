## 1. Source Configuration Split

- [x] 1.1 Create `sources.d/youtube_playlist.yaml` with `youtube_playlist` and `youtube_channel` entries from `youtube.yaml`
- [x] 1.2 Create `sources.d/youtube_rss.yaml` with `youtube_rss` entries from `youtube.yaml`
- [x] 1.3 Remove `sources.d/youtube.yaml`
- [x] 1.4 Add `hint_terms` list field to `YouTubePlaylistSource` model in `src/config/sources.py`
- [x] 1.5 Add `proofread` boolean field to `YouTubePlaylistSource` model (default: `true`)
- [x] 1.6 Verify `load_sources_directory` loads both new files correctly (existing behavior, no code changes expected)

## 2. Gemini Native YouTube Video Content Extraction

- [x] 2.1 Add `YOUTUBE_RSS_PROCESSING` to `ModelStep` enum in `src/config/models.py`
- [x] 2.2 Add `youtube_rss_processing` default model (`gemini-2.5-flash-lite`) to `src/config/model_registry.yaml` and `ModelConfig.__init__`
- [x] 2.3 Add `gemini_summary` (bool, default `true`) and `gemini_resolution` (str, default varies) fields to `YouTubePlaylistSource` and `YouTubeRSSSource` in `src/config/sources.py`
- [x] 2.4 Add `generate_with_video(model, system_prompt, user_prompt, video_url, media_resolution)` method to LLM router's Gemini backend in `src/services/llm_router.py`:
  - Use `Part.from_uri(file_uri=video_url, mime_type="video/mp4")` alongside text prompt
  - Accept `media_resolution` parameter (`LOW`, `MEDIUM`, `HIGH`, or `None` for default)
  - Pass `media_resolution` via `GenerateContentConfig`
- [x] 2.5 Create content extraction prompt for Gemini video processing — comprehensive coverage of all topics discussed, technical details, speaker statements, examples, and arguments (no editorial filtering; the summarization step handles relevance)
- [x] 2.6 Integrate Gemini content extraction into `YouTubeContentIngestionService.ingest_playlist()`:
  - Check `gemini_summary` config and `GOOGLE_API_KEY` availability
  - Call `generate_with_video()` with `YOUTUBE_PROCESSING` model step and source's `gemini_resolution`
  - Store Gemini output as Content `content` field (analogous to transcript) with `processing_method: gemini_native` in `metadata_json`
  - Content proceeds through normal summarization pipeline — no special handling
  - Fall back to transcript-based flow on error
- [x] 2.7 Integrate Gemini content extraction into `YouTubeRSSIngestionService.ingest_feed()`:
  - Use `YOUTUBE_RSS_PROCESSING` model step (gemini-2.5-flash-lite)
  - Default `gemini_resolution: low` for cost savings (66 tokens/frame vs 258)
  - Same fallback logic as playlists
- [x] 2.8 Update `youtube_playlist.yaml` and `youtube_rss.yaml` templates with `gemini_summary` and `gemini_resolution` defaults

## 3. LLM-Based Caption Proofreading

- [x] 3.1 Add `CAPTION_PROOFREADING` to `ModelStep` enum in `src/config/models.py`
- [x] 3.2 Add `caption_proofreading` default model (`gemini-2.5-flash-lite`) to `src/config/model_registry.yaml` and `ModelConfig.__init__`
- [x] 3.3 Create `src/ingestion/youtube_captions.py` module with:
  - `proofread_transcript(segments, hint_terms, is_auto_generated, model_step) -> list[TranscriptSegment]`
  - Batching logic (~50 segments per LLM call)
  - System prompt with hint terms, domain context, and sparse-diff output format
  - Response parser to apply corrections back to segments
- [x] 3.4 Define built-in default hint terms list for common AI terminology
- [x] 3.5 Add hint terms loading from YAML config (per-playlist additions merged with defaults)
- [x] 3.6 Integrate proofreading into `YouTubeContentIngestionService.ingest_playlist()` after transcript retrieval (only for transcript-based fallback path)
- [x] 3.7 Add `is_proofread` flag to Content `metadata_json`
- [x] 3.8 Skip proofreading for manual (non-auto-generated) captions

## 4. Exponential Backoff on 429 (Transcript Fallback)

- [x] 4.1 Add `_retry_with_backoff()` helper to `YouTubeClient` (or `youtube_captions.py`)
- [x] 4.2 Wrap `get_transcript()` youtube-transcript-api call with 429 retry logic
- [x] 4.3 Add `youtube_max_retries` (default: 4) and `youtube_backoff_base` (default: 2.0) settings to `src/config/settings.py`
- [x] 4.4 Add ±20% jitter to backoff delays

## 5. Cloud OAuth Support

- [x] 5.1 Add `youtube_oauth_token_json` setting to `src/config/settings.py` (from `YOUTUBE_OAUTH_TOKEN_JSON` env var)
- [x] 5.2 Add token hydration logic to `YouTubeClient._authenticate_oauth()`: write env var content to token file if file doesn't exist
- [x] 5.3 Add clear error message when refresh token is revoked (with re-generation instructions)
- [x] 5.4 Exclude `YOUTUBE_OAUTH_TOKEN_JSON` from `railway_env_sync.py` sensitive patterns (if needed)

## 6. Orchestrator and CLI Commands

**Prerequisite:** `refactor-ingestion-orchestrator` must be implemented first. The orchestrator provides `ingest_youtube()` which this proposal splits into two functions.

- [x] 6.1 Split `ingest_youtube()` in `src/ingestion/orchestrator.py` into `ingest_youtube_playlist()` and `ingest_youtube_rss()` — each wraps the corresponding service class
- [x] 6.2 Update `ingest_youtube()` to call both sequentially (playlists first, backward compatible)
- [x] 6.3 Add `aca ingest youtube-playlist` command in `src/cli/ingest_commands.py` — delegates to `ingest_youtube_playlist()` orchestrator function
- [x] 6.4 Add `aca ingest youtube-rss` command in `src/cli/ingest_commands.py` — delegates to `ingest_youtube_rss()` orchestrator function
- [x] 6.5 Update `aca ingest youtube` to call `ingest_youtube_playlist()` then `ingest_youtube_rss()` via orchestrator

## 7. Pipeline and Task Worker Split

Since the orchestrator centralizes wiring, pipeline and task worker changes are minimal.

- [x] 7.1 Update pipeline's `_run_ingestion_stage_async()` to call `ingest_youtube_playlist()` and `ingest_youtube_rss()` as two separate parallel tasks (replacing single `ingest_youtube()` call)
- [x] 7.2 Update task count from 5 to 6 in pipeline progress reporting
- [x] 7.3 Report `youtube-playlist` and `youtube-rss` counts separately in pipeline results
- [x] 7.4 Add `youtube-playlist` and `youtube-rss` as valid source values in task worker's `ingest_content` entrypoint (routing to respective orchestrator functions)

## 8. Service Integration

- [x] 8.1 Wire Gemini content extraction and proofreading from source config into `ingest_playlist()`
- [x] 8.2 Wire Gemini content extraction into `YouTubeRSSIngestionService.ingest_feed()`
- [x] 8.3 Ensure transcript-based fallback works correctly when Gemini is unavailable or disabled
- [x] 8.4 Verify Gemini-ingested content flows through normal `aca summarize pending` pipeline without special handling

## 9. Tests

- [x] 9.1 Add `tests/test_services/test_llm_router_video.py`:
  - `generate_with_video()` with mocked Gemini client
  - `media_resolution` parameter forwarding (LOW, default)
  - `Part.from_uri` construction with YouTube URL
  - Error handling for unavailable videos
- [x] 9.2 Add Gemini content extraction integration tests for playlist ingestion:
  - Gemini output stored as Content `content` field with `processing_method: gemini_native` in metadata
  - Content proceeds through normal summarization pipeline (no special handling)
  - Fallback to transcript when `GOOGLE_API_KEY` not set
  - Fallback when Gemini returns error for specific video
  - `gemini_summary: false` disables Gemini path
- [x] 9.3 Add Gemini content extraction integration tests for RSS ingestion:
  - Uses `YOUTUBE_RSS_PROCESSING` model step (flash-lite)
  - Uses `media_resolution: LOW` by default
  - Fallback to transcript-based flow
- [x] 9.4 Add `tests/test_ingestion/test_youtube_captions.py`:
  - LLM proofread function (mocked LLM responses, batch splitting, sparse-diff parsing)
  - Hint terms merging (built-in defaults + per-playlist additions)
  - Skip manual captions
  - Proofread disabled via `proofread: false`
- [x] 9.6 Update `tests/test_ingestion/test_youtube_sources.py` for split YAML files
- [x] 9.7 Add CLI tests for `youtube-playlist` and `youtube-rss` subcommands (mock orchestrator functions)
- [x] 9.8 Add tests for 429 exponential backoff (mock 429 responses, verify retry count and delays)
- [x] 9.9 Add tests for cloud OAuth token hydration (env var → file, file precedence, revoked token)
- [x] 9.10 Add tests for pipeline split — mock `ingest_youtube_playlist()` and `ingest_youtube_rss()` orchestrator functions as separate parallel tasks
- [x] 9.11 Add tests for task worker `youtube-playlist` and `youtube-rss` source routing to orchestrator functions

## 10. Documentation

- [x] 10.1 Update CLAUDE.md source configuration section with split YAML example and Gemini summary config
- [x] 10.2 Update CLAUDE.md key commands section with new CLI commands
- [x] 10.3 Add Gemini native summarization configuration to CLAUDE.md (model tiers, resolution control)
- [x] 10.4 Add proofreading configuration example to CLAUDE.md
- [x] 10.5 Add cloud OAuth setup instructions to docs/SETUP.md
- [x] 10.6 Add 429 backoff settings to docs/SETUP.md environment variables section
- [x] 10.7 Add `YOUTUBE_RSS_PROCESSING` model step to docs/MODEL_CONFIGURATION.md
