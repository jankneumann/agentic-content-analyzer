## 1. Source Configuration Foundation

- [ ] 1.1 Create `src/config/sources.py` with Pydantic models for source config (`SourceBase`, `RSSSource`, `YouTubePlaylistSource` with `visibility` field, `YouTubeChannelSource` with `visibility` field, `YouTubeRSSSource`, `PodcastSource`, `GmailSource`, `SourcesConfig`)
- [ ] 1.2 Add `SOURCES_CONFIG_FILE` setting to `src/config/settings.py` (default: `sources.yaml`)
- [ ] 1.3 Add `get_sources_config()` method to Settings that loads and validates `sources.yaml`
- [ ] 1.4 Implement fallback logic: if `sources.yaml` missing, read from `rss_feeds.txt` + `youtube_playlists.txt`
- [ ] 1.5 Write unit tests for source config parsing, validation, and fallback behavior

## 2. Migration Tooling

- [ ] 2.1 Create migration script `src/config/migrate_sources.py` with CLI entry point
- [ ] 2.2 Implement `rss_feeds.txt` → YAML converter (preserving comments as tags)
- [ ] 2.3 Implement `youtube_playlists.txt` → YAML converter (preserving descriptions)
- [ ] 2.4 Implement `AI-ML-Data-News.md` parser to extract RSS feeds, podcast feeds, and YouTube channels with names
- [ ] 2.5 Implement deduplication across all inputs (by URL/ID)
- [ ] 2.6 Generate initial `sources.yaml` from existing config + markdown reference
- [ ] 2.7 Write tests for migration script (markdown parsing, dedup, output format)

## 3. RSS Ingestion Integration

- [ ] 3.1 Update `RSSContentIngestionService` to accept sources from `SourcesConfig` instead of raw URL list
- [ ] 3.2 Filter by `enabled` flag and `type: rss` from config
- [ ] 3.3 Pass per-source `max_entries` override to `fetch_content()`
- [ ] 3.4 Include source `name` and `tags` in Content `metadata_json`
- [ ] 3.5 Update tests for new config-driven RSS ingestion

## 4. YouTube Visibility & OAuth Graceful Degradation

- [ ] 4.1 Add `visibility` field (`public`/`private`) to `YouTubePlaylistSource` and `YouTubeChannelSource` models
- [ ] 4.2 Refactor `YouTubeClient.__init__()` to catch `RefreshError` on OAuth, fall back to API key, and set `self.oauth_available` flag
- [ ] 4.3 Update `ingest_all_playlists()` to skip `visibility: private` sources when `oauth_available=False`, log warning per skipped source
- [ ] 4.4 Write tests for OAuth fallback behavior (mock expired token → verify public sources still ingested)

## 5. YouTube Channel Support

- [ ] 5.1 Add `resolve_channel_to_playlist()` method to `YouTubeClient` using `channels().list(part="contentDetails")`
- [ ] 5.2 Cache channel→playlist ID mappings (in-memory or file-based) to avoid repeated API calls
- [ ] 5.3 Update `YouTubeContentIngestionService.ingest_all_playlists()` to handle channel sources
- [ ] 5.4 Write integration test for channel→playlist resolution (mock YouTube API)

## 6. YouTube RSS Feed Support

- [ ] 6.1 Add `YouTubeRSSIngestionService` or extend existing service to handle YouTube RSS feeds
- [ ] 6.2 Parse YouTube RSS feeds with feedparser to extract video IDs and metadata
- [ ] 6.3 Reuse existing transcript fetching (`YouTubeClient.get_transcript()`) for discovered videos
- [ ] 6.4 Deduplicate against existing YouTube content by video ID
- [ ] 6.5 Write tests for YouTube RSS parsing and video ID extraction

## 7. Podcast Ingestion (Transcript-First)

- [ ] 7.1 Add `ContentSource.PODCAST` to enum in `src/models/content.py`
- [ ] 7.2 Create Alembic migration for new enum value
- [ ] 7.3 Create `src/ingestion/podcast.py` with `PodcastClient` and `PodcastContentIngestionService`
- [ ] 7.4 Implement Tier 1: feed-embedded transcript extraction from `<content:encoded>`, `<description>`, `<itunes:summary>` (use if ≥ 500 chars)
- [ ] 7.5 Implement Tier 2: linked transcript page detection — scan show notes for `/transcript`, `/show-notes` URLs, fetch via Trafilatura
- [ ] 7.6 Implement Tier 3 (audio fallback): audio download to temp storage with size/duration limits, gated by `transcribe: true`
- [ ] 7.7 Implement OpenAI Whisper API transcription (`src/ingestion/podcast_transcriber.py`) for Tier 3
- [ ] 7.8 Convert transcripts (all tiers) to markdown format, with timestamps where available (Tier 3 Whisper output)
- [ ] 7.9 Add podcast-specific settings: `PODCAST_STT_PROVIDER`, `PODCAST_MAX_DURATION_MINUTES`, `PODCAST_TEMP_DIR`
- [ ] 7.10 Implement dedup using `source_id=podcast:{episode_guid}` pattern
- [ ] 7.11 Store `raw_format` per tier: `feed_transcript`, `linked_transcript`, or `audio_transcript`
- [ ] 7.12 Write unit tests for all 3 transcript tiers, fallback logic, and markdown conversion
- [ ] 7.13 Write integration test for end-to-end podcast ingestion (mock feed with embedded transcript, mock STT API)

## 8. API Integration

- [ ] 8.1 Add `PODCAST` to supported sources in `_run_content_ingestion()` in `content_routes.py`
- [ ] 8.2 Update `IngestContentsDialog.tsx` to include Podcast tab in source selector
- [ ] 8.3 Add source config API endpoint: `GET /api/v1/sources` (list configured sources with counts and status)
- [ ] 8.4 Write E2E test for podcast ingestion trigger from UI

## 9. Documentation

- [ ] 9.1 Update `CLAUDE.md` with `sources.yaml` configuration reference and YouTube visibility flag
- [ ] 9.2 Update `docs/SETUP.md` with source configuration instructions and podcast STT setup
- [ ] 9.3 Update `docs/ARCHITECTURE.md` ingestion section with new source types and transcript-first strategy
- [ ] 9.4 Add migration guide for transitioning from `rss_feeds.txt` / `youtube_playlists.txt`
