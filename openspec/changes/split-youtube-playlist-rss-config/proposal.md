# Change: Split YouTube Playlist and RSS Source Configuration

## Why

The current `youtube.yaml` file mixes two ingestion paths with fundamentally different API strategies and rate-limit profiles:

1. **Playlist ingestion** uses the YouTube Data API (10k quota units/day) for video discovery and can use the Data API `captions` endpoint for transcript retrieval under OAuth — no IP-based rate limiting.
2. **RSS ingestion** uses feedparser for discovery and `youtube-transcript-api` for transcripts — the transcript library scrapes YouTube, triggering IP blocks when processing 60+ channels.

Because both share a single config file and a single CLI command, they cannot be run independently. A rate-limit failure in RSS transcript fetching stalls the entire YouTube ingestion, including the quota-based playlist path that would otherwise succeed.

Splitting the configuration and CLI entry points lets operators:
- Run playlist ingestion (Data API captions, quota-managed) on a frequent schedule without fear of IP blocks.
- Run RSS ingestion (youtube-transcript-api) on a separate, throttled schedule.
- Monitor and tune each path independently.

## What Changes

### Source Configuration Split
- Split `sources.d/youtube.yaml` into `sources.d/youtube_playlist.yaml` (playlist + channel sources) and `sources.d/youtube_rss.yaml` (RSS feed sources).
- `YouTubeContentIngestionService.ingest_all_playlists()` reads from `youtube_playlist.yaml`.
- `YouTubeRSSIngestionService.ingest_all_feeds()` reads from `youtube_rss.yaml`.
- The source loading mechanism (`load_sources_directory`) is unchanged — it already loads all `*.yaml` files, so the split is transparent to the loader.

### YouTube Data API Captions for Playlists
- Add `YouTubeClient.get_transcript_via_api()` method that uses `captions.list` + `captions.download` endpoints.
- When OAuth is available: use Data API captions for playlist videos (avoids youtube-transcript-api rate limits entirely).
- When only API key is available: fall back to `youtube-transcript-api` for transcripts (captions.download requires OAuth).
- The `get_transcript()` method gains a `prefer_data_api: bool` parameter (default `True` for playlist service, `False` for RSS service).

### CLI Command Split
- Add `aca ingest youtube-playlist` — ingests only playlist and channel sources from `youtube_playlist.yaml`.
- Add `aca ingest youtube-rss` — ingests only RSS feed sources from `youtube_rss.yaml`.
- Keep `aca ingest youtube` as a combined command that runs both (backward compatible).

### Caption Proofreading
- Add a post-processing proofread step for YouTube captions that corrects phonetic misspellings of proper nouns (e.g., "cloud"/"clawd" → "Claude", "open eye" → "OpenAI").
- Configurable via a corrections dictionary in `sources.d/youtube_playlist.yaml` or a dedicated `youtube_corrections.yaml` file.
- Applied after transcript retrieval, before markdown conversion.
- Supports both static dictionary replacements and optional LLM-based proofread for ambiguous cases.

### Quota Awareness
- Log Data API quota usage per run (captions.list = 50 units, captions.download = 200 units per video).
- Add `YOUTUBE_PREFER_DATA_API_CAPTIONS` setting (default: `true`) to control whether playlist ingestion prefers the Data API captions path.

## Impact

### Affected Specs
- `source-configuration` — new file-split convention, Data API captions transcript strategy
- `cli-interface` — new subcommands for split ingestion

### Affected Code
- `sources.d/youtube.yaml` — split into two files
- `src/ingestion/youtube.py` — `YouTubeClient.get_transcript_via_api()`, transcript method routing, caption proofreading
- `src/ingestion/youtube_captions.py` — new module: SRT parser, proofread function, corrections loader
- `src/config/settings.py` — new `youtube_prefer_data_api_captions` setting
- `src/cli/ingest_commands.py` — new subcommands
- `tests/test_ingestion/test_youtube.py` — Data API captions tests
- `tests/test_ingestion/test_youtube_captions.py` — SRT parsing, proofread tests
- `tests/test_ingestion/test_youtube_rss.py` — config file path update

### Breaking Changes
- **None** — `aca ingest youtube` continues to work as before. The YAML split is transparent to `load_sources_directory` since it loads all `*.yaml` files. Existing automation calling `aca ingest youtube` is unaffected.

### Quota Budget
- `captions.list`: 50 quota units per video
- `captions.download`: 200 quota units per video
- Per video total: 250 units (+ 1 unit for playlistItems.list)
- With 10k daily quota: ~40 playlist videos/day via Data API captions
- RSS feeds: zero quota usage (feedparser + youtube-transcript-api)
