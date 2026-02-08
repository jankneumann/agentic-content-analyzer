## 1. Source Configuration Split

- [ ] 1.1 Create `sources.d/youtube_playlist.yaml` with `youtube_playlist` and `youtube_channel` entries from `youtube.yaml`
- [ ] 1.2 Create `sources.d/youtube_rss.yaml` with `youtube_rss` entries from `youtube.yaml`
- [ ] 1.3 Remove `sources.d/youtube.yaml`
- [ ] 1.4 Add `corrections` field support to `YouTubePlaylistSource` model in `src/config/sources.py`
- [ ] 1.5 Add `proofread` boolean field to `YouTubePlaylistSource` model (default: `true`)
- [ ] 1.6 Verify `load_sources_directory` loads both new files correctly (existing behavior, no code changes expected)

## 2. YouTube Data API Captions

- [ ] 2.1 Create `src/ingestion/youtube_captions.py` module with:
  - SRT parser: `parse_srt(srt_content: str) -> list[TranscriptSegment]`
  - Caption track selector: `select_best_track(tracks, languages) -> track`
- [ ] 2.2 Add `YouTubeClient.get_transcript_via_api(video_id, languages)` method using `captions.list` + `captions.download`
- [ ] 2.3 Add `prefer_data_api` parameter to `YouTubeClient.get_transcript()` with fallback logic
- [ ] 2.4 Add `youtube_prefer_data_api_captions` setting to `src/config/settings.py` (default: `true`)
- [ ] 2.5 Add quota usage tracking and logging in `YouTubeClient`

## 3. Caption Proofreading

- [ ] 3.1 Add `proofread_transcript(segments, corrections, is_auto_generated) -> list[TranscriptSegment]` to `src/ingestion/youtube_captions.py`
- [ ] 3.2 Define built-in corrections dictionary for common AI terminology misspellings
- [ ] 3.3 Add corrections loading from YAML config (per-playlist overrides merged with defaults)
- [ ] 3.4 Integrate proofreading into `YouTubeContentIngestionService.ingest_playlist()` after transcript retrieval
- [ ] 3.5 Add `is_proofread` flag to Content `metadata_json`
- [ ] 3.6 Skip proofreading for manual (non-auto-generated) captions

## 4. CLI Commands

- [ ] 4.1 Add `aca ingest youtube-playlist` command in `src/cli/ingest_commands.py`
- [ ] 4.2 Add `aca ingest youtube-rss` command in `src/cli/ingest_commands.py`
- [ ] 4.3 Update `aca ingest youtube` to call both new commands sequentially (backward compatible)
- [ ] 4.4 Fix `service.ingest_all_feeds()` type ignore by creating `YouTubeRSSIngestionService` explicitly

## 5. Exponential Backoff on 429

- [ ] 5.1 Add `_retry_with_backoff()` helper to `YouTubeClient` (or `youtube_captions.py`)
- [ ] 5.2 Wrap `get_transcript()` youtube-transcript-api call with 429 retry logic
- [ ] 5.3 Wrap `get_transcript_via_api()` Data API calls with 429 retry logic
- [ ] 5.4 Add `youtube_max_retries` (default: 4) and `youtube_backoff_base` (default: 2.0) settings to `src/config/settings.py`
- [ ] 5.5 Add ±20% jitter to backoff delays

## 6. Cloud OAuth Support

- [ ] 6.1 Add `youtube_oauth_token_json` setting to `src/config/settings.py` (from `YOUTUBE_OAUTH_TOKEN_JSON` env var)
- [ ] 6.2 Add token hydration logic to `YouTubeClient._authenticate_oauth()`: write env var content to token file if file doesn't exist
- [ ] 6.3 Add clear error message when refresh token is revoked (with re-generation instructions)
- [ ] 6.4 Exclude `YOUTUBE_OAUTH_TOKEN_JSON` from `railway_env_sync.py` sensitive patterns (if needed)

## 7. Service Integration

- [ ] 7.1 Update `YouTubeContentIngestionService.ingest_all_playlists()` to pass `prefer_data_api=True` to transcript calls
- [ ] 7.2 Confirm `YouTubeRSSIngestionService` continues using `youtube-transcript-api` (no changes expected)
- [ ] 7.3 Wire proofreading corrections from source config into `ingest_playlist()`

## 8. Tests

- [ ] 8.1 Add `tests/test_ingestion/test_youtube_captions.py`:
  - SRT parsing (valid SRT, empty, malformed)
  - Caption track selection (manual vs auto, language preference)
  - Proofread function (basic replacements, case-insensitive, whole-word, skip manual captions)
- [ ] 8.2 Add tests for `YouTubeClient.get_transcript_via_api()` with mocked Data API responses
- [ ] 8.3 Add tests for Data API → youtube-transcript-api fallback
- [ ] 8.4 Update `tests/test_ingestion/test_youtube_sources.py` for split YAML files
- [ ] 8.5 Add CLI tests for `youtube-playlist` and `youtube-rss` subcommands
- [ ] 8.6 Add tests for 429 exponential backoff (mock 429 responses, verify retry count and delays)
- [ ] 8.7 Add tests for cloud OAuth token hydration (env var → file, file precedence, revoked token)

## 9. Documentation

- [ ] 9.1 Update CLAUDE.md source configuration section with split YAML example
- [ ] 9.2 Update CLAUDE.md key commands section with new CLI commands
- [ ] 9.3 Add proofreading configuration example to CLAUDE.md
- [ ] 9.4 Add quota budget note to CLAUDE.md critical gotchas table
- [ ] 9.5 Add cloud OAuth setup instructions to docs/SETUP.md
- [ ] 9.6 Add 429 backoff settings to docs/SETUP.md environment variables section
