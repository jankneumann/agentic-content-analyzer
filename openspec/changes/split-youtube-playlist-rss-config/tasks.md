## 1. Source Configuration Split

- [ ] 1.1 Create `sources.d/youtube_playlist.yaml` with `youtube_playlist` and `youtube_channel` entries from `youtube.yaml`
- [ ] 1.2 Create `sources.d/youtube_rss.yaml` with `youtube_rss` entries from `youtube.yaml`
- [ ] 1.3 Remove `sources.d/youtube.yaml`
- [ ] 1.4 Add `hint_terms` list field to `YouTubePlaylistSource` model in `src/config/sources.py`
- [ ] 1.5 Add `proofread` boolean field to `YouTubePlaylistSource` model (default: `true`)
- [ ] 1.6 Verify `load_sources_directory` loads both new files correctly (existing behavior, no code changes expected)

## 2. Gemini Native YouTube Video Content Extraction

- [ ] 2.1 Add `YOUTUBE_RSS_PROCESSING` to `ModelStep` enum in `src/config/models.py`
- [ ] 2.2 Add `youtube_rss_processing` default model (`gemini-2.5-flash-lite`) to `src/config/model_registry.yaml` and `ModelConfig.__init__`
- [ ] 2.3 Add `gemini_summary` (bool, default `true`) and `gemini_resolution` (str, default varies) fields to `YouTubePlaylistSource` and `YouTubeRSSSource` in `src/config/sources.py`
- [ ] 2.4 Add `generate_with_video(model, system_prompt, user_prompt, video_url, media_resolution)` method to LLM router's Gemini backend in `src/services/llm_router.py`:
  - Use `Part.from_uri(file_uri=video_url, mime_type="video/mp4")` alongside text prompt
  - Accept `media_resolution` parameter (`LOW`, `MEDIUM`, `HIGH`, or `None` for default)
  - Pass `media_resolution` via `GenerateContentConfig`
- [ ] 2.5 Create content extraction prompt for Gemini video processing — comprehensive coverage of all topics discussed, technical details, speaker statements, examples, and arguments (no editorial filtering; the summarization step handles relevance)
- [ ] 2.6 Integrate Gemini content extraction into `YouTubeContentIngestionService.ingest_playlist()`:
  - Check `gemini_summary` config and `GOOGLE_API_KEY` availability
  - Call `generate_with_video()` with `YOUTUBE_PROCESSING` model step and source's `gemini_resolution`
  - Store Gemini output as Content `content` field (analogous to transcript) with `processing_method: gemini_native` in `metadata_json`
  - Content proceeds through normal summarization pipeline — no special handling
  - Fall back to transcript-based flow on error
- [ ] 2.7 Integrate Gemini content extraction into `YouTubeRSSIngestionService.ingest_feed()`:
  - Use `YOUTUBE_RSS_PROCESSING` model step (gemini-2.5-flash-lite)
  - Default `gemini_resolution: low` for cost savings (66 tokens/frame vs 258)
  - Same fallback logic as playlists
- [ ] 2.8 Update `youtube_playlist.yaml` and `youtube_rss.yaml` templates with `gemini_summary` and `gemini_resolution` defaults

## 3. LLM-Based Caption Proofreading

- [ ] 3.1 Add `CAPTION_PROOFREADING` to `ModelStep` enum in `src/config/models.py`
- [ ] 3.2 Add `caption_proofreading` default model (`gemini-2.5-flash-lite`) to `src/config/model_registry.yaml` and `ModelConfig.__init__`
- [ ] 3.3 Create `src/ingestion/youtube_captions.py` module with:
  - `proofread_transcript(segments, hint_terms, is_auto_generated, model_step) -> list[TranscriptSegment]`
  - Batching logic (~50 segments per LLM call)
  - System prompt with hint terms, domain context, and sparse-diff output format
  - Response parser to apply corrections back to segments
- [ ] 3.4 Define built-in default hint terms list for common AI terminology
- [ ] 3.5 Add hint terms loading from YAML config (per-playlist additions merged with defaults)
- [ ] 3.6 Integrate proofreading into `YouTubeContentIngestionService.ingest_playlist()` after transcript retrieval (only for transcript-based fallback path)
- [ ] 3.7 Add `is_proofread` flag to Content `metadata_json`
- [ ] 3.8 Skip proofreading for manual (non-auto-generated) captions

## 4. Exponential Backoff on 429 (Transcript Fallback)

- [ ] 4.1 Add `_retry_with_backoff()` helper to `YouTubeClient` (or `youtube_captions.py`)
- [ ] 4.2 Wrap `get_transcript()` youtube-transcript-api call with 429 retry logic
- [ ] 4.3 Add `youtube_max_retries` (default: 4) and `youtube_backoff_base` (default: 2.0) settings to `src/config/settings.py`
- [ ] 4.4 Add ±20% jitter to backoff delays

## 5. Cloud OAuth Support

- [ ] 5.1 Add `youtube_oauth_token_json` setting to `src/config/settings.py` (from `YOUTUBE_OAUTH_TOKEN_JSON` env var)
- [ ] 5.2 Add token hydration logic to `YouTubeClient._authenticate_oauth()`: write env var content to token file if file doesn't exist
- [ ] 5.3 Add clear error message when refresh token is revoked (with re-generation instructions)
- [ ] 5.4 Exclude `YOUTUBE_OAUTH_TOKEN_JSON` from `railway_env_sync.py` sensitive patterns (if needed)

## 6. CLI Commands

- [ ] 6.1 Add `aca ingest youtube-playlist` command in `src/cli/ingest_commands.py`
- [ ] 6.2 Add `aca ingest youtube-rss` command in `src/cli/ingest_commands.py`
- [ ] 6.3 Update `aca ingest youtube` to call both sequentially (playlists first, backward compatible)
- [ ] 6.4 Fix `service.ingest_all_feeds()` type ignore by creating `YouTubeRSSIngestionService` explicitly

## 7. Pipeline Ingestion Split

- [ ] 7.1 Update `_run_ingestion_stage_async()` in `src/cli/pipeline_commands.py` to split YouTube into two parallel tasks: `youtube-playlist` and `youtube-rss`
- [ ] 7.2 Create `YouTubeRSSIngestionService` instance in pipeline (currently only `YouTubeContentIngestionService` is used)
- [ ] 7.3 Update task count from 5 to 6 in pipeline progress reporting
- [ ] 7.4 Report `youtube-playlist` and `youtube-rss` counts separately in pipeline results

## 8. Service Integration

- [ ] 8.1 Wire Gemini content extraction and proofreading from source config into `ingest_playlist()`
- [ ] 8.2 Wire Gemini content extraction into `YouTubeRSSIngestionService.ingest_feed()`
- [ ] 8.3 Ensure transcript-based fallback works correctly when Gemini is unavailable or disabled
- [ ] 8.4 Verify Gemini-ingested content flows through normal `aca summarize pending` pipeline without special handling

## 9. Tests

- [ ] 9.1 Add `tests/test_services/test_llm_router_video.py`:
  - `generate_with_video()` with mocked Gemini client
  - `media_resolution` parameter forwarding (LOW, default)
  - `Part.from_uri` construction with YouTube URL
  - Error handling for unavailable videos
- [ ] 9.2 Add Gemini content extraction integration tests for playlist ingestion:
  - Gemini output stored as Content `content` field with `processing_method: gemini_native` in metadata
  - Content proceeds through normal summarization pipeline (no special handling)
  - Fallback to transcript when `GOOGLE_API_KEY` not set
  - Fallback when Gemini returns error for specific video
  - `gemini_summary: false` disables Gemini path
- [ ] 9.3 Add Gemini content extraction integration tests for RSS ingestion:
  - Uses `YOUTUBE_RSS_PROCESSING` model step (flash-lite)
  - Uses `media_resolution: LOW` by default
  - Fallback to transcript-based flow
- [ ] 9.4 Add `tests/test_ingestion/test_youtube_captions.py`:
  - LLM proofread function (mocked LLM responses, batch splitting, sparse-diff parsing)
  - Hint terms merging (built-in defaults + per-playlist additions)
  - Skip manual captions
  - Proofread disabled via `proofread: false`
- [ ] 9.6 Update `tests/test_ingestion/test_youtube_sources.py` for split YAML files
- [ ] 9.7 Add CLI tests for `youtube-playlist` and `youtube-rss` subcommands
- [ ] 9.8 Add tests for 429 exponential backoff (mock 429 responses, verify retry count and delays)
- [ ] 9.9 Add tests for cloud OAuth token hydration (env var → file, file precedence, revoked token)
- [ ] 9.10 Add tests for pipeline split (youtube-playlist and youtube-rss as separate parallel tasks)

## 10. Documentation

- [ ] 10.1 Update CLAUDE.md source configuration section with split YAML example and Gemini summary config
- [ ] 10.2 Update CLAUDE.md key commands section with new CLI commands
- [ ] 10.3 Add Gemini native summarization configuration to CLAUDE.md (model tiers, resolution control)
- [ ] 10.4 Add proofreading configuration example to CLAUDE.md
- [ ] 10.5 Add cloud OAuth setup instructions to docs/SETUP.md
- [ ] 10.6 Add 429 backoff settings to docs/SETUP.md environment variables section
- [ ] 10.7 Add `YOUTUBE_RSS_PROCESSING` model step to docs/MODEL_CONFIGURATION.md
