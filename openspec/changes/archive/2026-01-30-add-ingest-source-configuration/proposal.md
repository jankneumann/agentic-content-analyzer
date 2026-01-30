# Change: Add Unified Ingestion Source Configuration

## Why

Ingestion source definitions are currently scattered across three separate files with inconsistent formats (`rss_feeds.txt`, `youtube_playlists.txt`, and `.env` for Gmail). This makes it difficult to:
- Add new source types (YouTube channels, podcast RSS feeds)
- Manage sources with metadata (names, tags, enable/disable)
- Maintain a single source of truth for all content sources
- Support per-source configuration (e.g., transcript language preferences, max entries)

Additionally, two important source types are not yet supported:
- **YouTube channels** — discoverable via channel ID → uploads playlist conversion
- **Podcast RSS feeds** — standard RSS with `<enclosure>` audio elements requiring transcription

## What Changes

- **New `sources.d/` config directory** — split by source type (`rss.yaml`, `youtube.yaml`, `podcasts.yaml`, `gmail.yaml`) for manageability at scale; single `sources.yaml` also supported
- **YAML format** with per-source metadata (name, tags, enabled, source-specific options)
- **New `ContentSource.PODCAST` enum value** for podcast content
- **YouTube playlist support** — existing `youtube_playlists.txt` entries migrate to `type: youtube_playlist` with visibility flag
- **YouTube channel support** — auto-resolve channel IDs to upload playlist IDs via YouTube Data API
- **YouTube RSS feed support** — parse `youtube.com/feeds/videos.xml?channel_id=` feeds via feedparser
- **Podcast RSS feed support** — transcript-first ingestion: check feed-embedded text, linked transcript pages, then audio STT as last resort
- **YouTube visibility flag** — `public`/`private` per playlist/channel; graceful OAuth degradation (skip private, continue public via API key)
- **Backward compatibility** — existing `rss_feeds.txt` and `youtube_playlists.txt` continue to work as fallbacks
- **Settings integration** — `SOURCES_CONFIG_DIR` and `SOURCES_CONFIG_FILE` env vars for custom paths
- **Migration script** — convert existing config files + `AI-ML-Data-News.md` into `sources.d/` or `sources.yaml`

### Out of Scope
- UI-based source management (future work)
- Real-time feed health monitoring
- Automatic source discovery

## Impact

- Affected specs: None (new capability: `source-configuration`)
- Affected code:
  - `src/config/settings.py` — new `get_sources_config()` method, `SOURCES_CONFIG_DIR` + `SOURCES_CONFIG_FILE` settings
  - `src/config/sources.py` — new module: YAML parser, directory loader, source models, migration utilities
  - `src/ingestion/rss.py` — consume sources from config, distinguish article vs podcast feeds
  - `src/ingestion/youtube.py` — support playlists, channel IDs, and RSS feeds from unified config
  - `src/ingestion/podcast.py` — **new module**: podcast RSS ingestion with transcript-first strategy + STT fallback
  - `src/models/content.py` — add `ContentSource.PODCAST` enum value
  - `src/api/content_routes.py` — add `PODCAST` to supported ingestion sources
  - `sources.d/` — new config directory (project root), split by source type
  - `AI-ML-Data-News.md` — reference data for initial source population
