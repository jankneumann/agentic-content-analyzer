## 1. Source Configuration Split

- [ ] 1.1 Create `sources.d/youtube_playlist.yaml` with `youtube_playlist` and `youtube_channel` entries from `youtube.yaml`
- [ ] 1.2 Create `sources.d/youtube_rss.yaml` with `youtube_rss` entries from `youtube.yaml`
- [ ] 1.3 Remove `sources.d/youtube.yaml`
- [ ] 1.4 Add `hint_terms` list field to `YouTubePlaylistSource` model in `src/config/sources.py`
- [ ] 1.5 Add `proofread` boolean field to `YouTubePlaylistSource` model (default: `true`)
- [ ] 1.6 Verify `load_sources_directory` loads both new files correctly (existing behavior, no code changes expected)

## 2. LLM-Based Caption Proofreading

- [ ] 2.1 Add `CAPTION_PROOFREADING` to `ModelStep` enum in `src/config/models.py`
- [ ] 2.2 Add `caption_proofreading` default model (`gemini-2.5-flash-lite`) to `src/config/model_registry.yaml` and `ModelConfig.__init__`
- [ ] 2.3 Create `src/ingestion/youtube_captions.py` module with:
  - `proofread_transcript(segments, hint_terms, is_auto_generated, model_step) -> list[TranscriptSegment]`
  - Batching logic (~50 segments per LLM call)
  - System prompt with hint terms, domain context, and sparse-diff output format
  - Response parser to apply corrections back to segments
- [ ] 2.4 Define built-in default hint terms list for common AI terminology
- [ ] 2.5 Add hint terms loading from YAML config (per-playlist additions merged with defaults)
- [ ] 2.6 Integrate proofreading into `YouTubeContentIngestionService.ingest_playlist()` after transcript retrieval
- [ ] 2.7 Add `is_proofread` flag to Content `metadata_json`
- [ ] 2.8 Skip proofreading for manual (non-auto-generated) captions

## 3. Exponential Backoff on 429

- [ ] 3.1 Add `_retry_with_backoff()` helper to `YouTubeClient` (or `youtube_captions.py`)
- [ ] 3.2 Wrap `get_transcript()` youtube-transcript-api call with 429 retry logic
- [ ] 3.3 Add `youtube_max_retries` (default: 4) and `youtube_backoff_base` (default: 2.0) settings to `src/config/settings.py`
- [ ] 3.4 Add ±20% jitter to backoff delays

## 4. Cloud OAuth Support

- [ ] 4.1 Add `youtube_oauth_token_json` setting to `src/config/settings.py` (from `YOUTUBE_OAUTH_TOKEN_JSON` env var)
- [ ] 4.2 Add token hydration logic to `YouTubeClient._authenticate_oauth()`: write env var content to token file if file doesn't exist
- [ ] 4.3 Add clear error message when refresh token is revoked (with re-generation instructions)
- [ ] 4.4 Exclude `YOUTUBE_OAUTH_TOKEN_JSON` from `railway_env_sync.py` sensitive patterns (if needed)

## 5. CLI Commands

- [ ] 5.1 Add `aca ingest youtube-playlist` command in `src/cli/ingest_commands.py`
- [ ] 5.2 Add `aca ingest youtube-rss` command in `src/cli/ingest_commands.py`
- [ ] 5.3 Update `aca ingest youtube` to call both sequentially (playlists first, backward compatible)
- [ ] 5.4 Fix `service.ingest_all_feeds()` type ignore by creating `YouTubeRSSIngestionService` explicitly

## 6. Pipeline Ingestion Split

- [ ] 6.1 Update `_run_ingestion_stage_async()` in `src/cli/pipeline_commands.py` to split YouTube into two parallel tasks: `youtube-playlist` and `youtube-rss`
- [ ] 6.2 Create `YouTubeRSSIngestionService` instance in pipeline (currently only `YouTubeContentIngestionService` is used)
- [ ] 6.3 Update task count from 5 to 6 in pipeline progress reporting
- [ ] 6.4 Report `youtube-playlist` and `youtube-rss` counts separately in pipeline results

## 7. Service Integration

- [ ] 7.1 Wire proofreading corrections from source config into `ingest_playlist()`
- [ ] 7.2 Confirm `YouTubeRSSIngestionService` continues using `youtube-transcript-api` (no changes expected)

## 8. Tests

- [ ] 8.1 Add `tests/test_ingestion/test_youtube_captions.py`:
  - LLM proofread function (mocked LLM responses, batch splitting, sparse-diff parsing)
  - Hint terms merging (built-in defaults + per-playlist additions)
  - Skip manual captions
  - Proofread disabled via `proofread: false`
- [ ] 8.2 Update `tests/test_ingestion/test_youtube_sources.py` for split YAML files
- [ ] 8.3 Add CLI tests for `youtube-playlist` and `youtube-rss` subcommands
- [ ] 8.4 Add tests for 429 exponential backoff (mock 429 responses, verify retry count and delays)
- [ ] 8.5 Add tests for cloud OAuth token hydration (env var → file, file precedence, revoked token)
- [ ] 8.6 Add tests for pipeline split (youtube-playlist and youtube-rss as separate parallel tasks)

## 9. Documentation

- [ ] 9.1 Update CLAUDE.md source configuration section with split YAML example
- [ ] 9.2 Update CLAUDE.md key commands section with new CLI commands
- [ ] 9.3 Add proofreading configuration example to CLAUDE.md
- [ ] 9.4 Add cloud OAuth setup instructions to docs/SETUP.md
- [ ] 9.5 Add 429 backoff settings to docs/SETUP.md environment variables section
