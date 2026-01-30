## 1. Source Configuration Foundation

- [x] 1.1 Create `src/config/sources.py` with Pydantic models for source config (`SourceBase`, `RSSSource`, `YouTubePlaylistSource` with `visibility` field, `YouTubeChannelSource` with `visibility` field, `YouTubeRSSSource`, `PodcastSource`, `GmailSource`, `SourcesConfig`)
- [x] 1.2 Add `SOURCES_CONFIG_DIR` and `SOURCES_CONFIG_FILE` settings to `src/config/settings.py` (defaults: `sources.d` and `sources.yaml`)
- [x] 1.3 Implement `sources.d/` directory loader: scan `*.yaml` files alphabetically, apply cascading defaults (`_defaults.yaml` globals → per-file `defaults` → per-entry fields), merge all `sources` lists
- [x] 1.4 Add `get_sources_config()` method to Settings with three-tier resolution: `sources.d/` → `sources.yaml` → legacy fallback
- [x] 1.5 Implement legacy fallback logic: if neither `sources.d/` nor `sources.yaml` exist, read from `rss_feeds.txt` + `youtube_playlists.txt`
- [x] 1.6 Write unit tests for source config parsing, validation, directory loading, per-file defaults (including `type` default), cascading default resolution, single-file loading, and fallback behavior

## 2. Migration Tooling

- [x] 2.1 Create migration script `src/config/migrate_sources.py` with CLI entry point
- [x] 2.2 Implement `rss_feeds.txt` → YAML converter (preserving comments as tags)
- [x] 2.3 Implement `youtube_playlists.txt` → YAML converter (preserving descriptions)
- [x] 2.4 Implement `AI-ML-Data-News.md` parser to extract RSS feeds, podcast feeds, and YouTube channels with names
- [x] 2.5 Implement deduplication across all inputs (by URL/ID)
- [x] 2.6 Implement `--output-dir sources.d` mode: split by type into `_defaults.yaml`, `rss.yaml`, `youtube.yaml`, `podcasts.yaml`, `gmail.yaml`
- [x] 2.7 Implement `--output sources.yaml` mode: single merged file (for simpler setups)
- [x] 2.8 Generate initial `sources.d/` from existing config + markdown reference
- [x] 2.9 Write tests for migration script (markdown parsing, dedup, split output, single file output)

## 3. RSS Ingestion Integration

- [x] 3.1 Update `RSSContentIngestionService` to accept sources from `SourcesConfig` instead of raw URL list
- [x] 3.2 Filter by `enabled` flag and `type: rss` from config
- [x] 3.3 Pass per-source `max_entries` override to `fetch_content()`
- [x] 3.4 Include source `name` and `tags` in Content `metadata_json`
- [x] 3.5 Update tests for new config-driven RSS ingestion

## 4. YouTube Visibility & OAuth Graceful Degradation

- [x] 4.1 Add `visibility` field (`public`/`private`) to `YouTubePlaylistSource` and `YouTubeChannelSource` models
- [x] 4.2 Refactor `YouTubeClient.__init__()` to catch `RefreshError` on OAuth, fall back to API key, and set `self.oauth_available` flag
- [x] 4.3 Update `ingest_all_playlists()` to skip `visibility: private` sources when `oauth_available=False`, log warning per skipped source
- [x] 4.4 Write tests for OAuth fallback behavior (mock expired token → verify public sources still ingested)

## 5. YouTube Channel Support

- [x] 5.1 Add `resolve_channel_to_playlist()` method to `YouTubeClient` using `channels().list(part="contentDetails")`
- [x] 5.2 Cache channel→playlist ID mappings (in-memory or file-based) to avoid repeated API calls
- [x] 5.3 Update `YouTubeContentIngestionService.ingest_all_playlists()` to handle channel sources
- [x] 5.4 Write integration test for channel→playlist resolution (mock YouTube API)

## 6. YouTube RSS Feed Support

- [x] 6.1 Add `YouTubeRSSIngestionService` or extend existing service to handle YouTube RSS feeds
- [x] 6.2 Parse YouTube RSS feeds with feedparser to extract video IDs and metadata
- [x] 6.3 Reuse existing transcript fetching (`YouTubeClient.get_transcript()`) for discovered videos
- [x] 6.4 Deduplicate against existing YouTube content by video ID
- [x] 6.5 Write tests for YouTube RSS parsing and video ID extraction

## 7. Podcast Ingestion (Transcript-First)

- [x] 7.1 Add `ContentSource.PODCAST` to enum in `src/models/content.py`
- [x] 7.2 Create Alembic migration for new enum value
- [x] 7.3 Create `src/ingestion/podcast.py` with `PodcastClient` and `PodcastContentIngestionService`
- [x] 7.4 Implement Tier 1: feed-embedded transcript extraction from `<content:encoded>`, `<description>`, `<itunes:summary>` (use if ≥ 500 chars)
- [x] 7.5 Implement Tier 2: linked transcript page detection — scan show notes for `/transcript`, `/show-notes` URLs, fetch via Trafilatura
- [x] 7.6 Implement Tier 3 (audio fallback): audio download to temp storage with size/duration limits, gated by `transcribe: true`
- [x] 7.7 Implement OpenAI Whisper API transcription (`src/ingestion/podcast_transcriber.py`) for Tier 3
- [x] 7.8 Convert transcripts (all tiers) to markdown format, with timestamps where available (Tier 3 Whisper output)
- [x] 7.9 Add podcast-specific settings: `PODCAST_STT_PROVIDER`, `PODCAST_MAX_DURATION_MINUTES`, `PODCAST_TEMP_DIR`
- [x] 7.10 Implement dedup using `source_id=podcast:{episode_guid}` pattern
- [x] 7.11 Store `raw_format` per tier: `feed_transcript`, `linked_transcript`, or `audio_transcript`
- [x] 7.12 Write unit tests for all 3 transcript tiers, fallback logic, and markdown conversion
- [x] 7.13 Write integration test for end-to-end podcast ingestion (mock feed with embedded transcript, mock STT API)

## 8. API Integration

- [x] 8.1 Add `PODCAST` to supported sources in `_run_content_ingestion()` in `content_routes.py`
- [x] 8.2 Update `IngestContentsDialog.tsx` to include Podcast tab in source selector
- [x] 8.3 Add source config API endpoint: `GET /api/v1/sources` (list configured sources with counts and status)
- [x] 8.4 Write E2E test for podcast ingestion trigger from UI

## 9. Documentation

- [x] 9.1 Update `CLAUDE.md` with `sources.yaml` configuration reference and YouTube visibility flag
- [x] 9.2 Update `docs/SETUP.md` with source configuration instructions and podcast STT setup
- [x] 9.3 Update `docs/ARCHITECTURE.md` ingestion section with new source types and transcript-first strategy
- [x] 9.4 Add migration guide for transitioning from `rss_feeds.txt` / `youtube_playlists.txt`
