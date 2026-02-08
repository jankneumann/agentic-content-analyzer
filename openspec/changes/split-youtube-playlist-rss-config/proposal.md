# Change: Split YouTube Playlist and RSS Source Configuration

## Why

The current `youtube.yaml` file mixes two ingestion paths that share a single CLI command and cannot be run independently. Both paths use `youtube-transcript-api` for transcript fetching, which scrapes YouTube and triggers IP blocks when processing 60+ channels in a single run.

The curated playlists (hand-picked interesting videos) are higher priority than the broad RSS channel feeds, but a rate-limit failure in RSS transcript fetching stalls the entire YouTube ingestion — including the playlists.

Splitting the configuration and CLI entry points lets operators:
- Run playlist ingestion first (fewer videos, higher priority) on a frequent schedule.
- Run RSS ingestion (60+ channels) on a separate, throttled schedule to stay under rate limits.
- Add exponential backoff so transient 429 errors are retried instead of immediately failing.
- Monitor and tune each path independently.

## What Changes

### Source Configuration Split
- Split `sources.d/youtube.yaml` into `sources.d/youtube_playlist.yaml` (playlist + channel sources) and `sources.d/youtube_rss.yaml` (RSS feed sources).
- `YouTubeContentIngestionService.ingest_all_playlists()` reads from `youtube_playlist.yaml`.
- `YouTubeRSSIngestionService.ingest_all_feeds()` reads from `youtube_rss.yaml`.
- The source loading mechanism (`load_sources_directory`) is unchanged — it already loads all `*.yaml` files, so the split is transparent to the loader.

### CLI Command Split
- Add `aca ingest youtube-playlist` — ingests only playlist and channel sources from `youtube_playlist.yaml`.
- Add `aca ingest youtube-rss` — ingests only RSS feed sources from `youtube_rss.yaml`.
- Keep `aca ingest youtube` as a combined command that runs both (backward compatible).

### Pipeline Ingestion Split
- Update `_run_ingestion_stage_async()` in `src/cli/pipeline_commands.py` to run `youtube-playlist` and `youtube-rss` as separate parallel ingestion tasks (currently only `ingest_all_playlists()` runs — RSS feeds are missing from the pipeline entirely).
- Both tasks run concurrently alongside Gmail, RSS, Podcast, and Substack sources.
- Report counts separately: `youtube-playlist: N items`, `youtube-rss: M items`.

### LLM-Based Caption Proofreading
- Add a post-processing proofread step using a fast LLM (default: `gemini-2.5-flash-lite` or `claude-haiku-4-5`) to contextually correct phonetic misspellings of proper nouns in auto-generated captions.
- A static dictionary cannot reliably handle words like "cloud" (legitimate in cloud computing) vs "Claude" (misspelling). The LLM uses surrounding context to disambiguate.
- Add `CAPTION_PROOFREADING` as a new `ModelStep` configurable via `MODEL_CAPTION_PROOFREADING` env var.
- Configurable `hint_terms` list per playlist in `youtube_playlist.yaml` to guide the LLM (e.g., "Claude", "Anthropic", "OpenAI").
- Applied after transcript retrieval, before markdown conversion. Only for auto-generated captions.
- Transcript segments sent in batches (~50 at a time) to minimize LLM calls. Estimated cost: ~$0.001-0.005 per video.

### Exponential Backoff on 429 Rate Limiting
- Add retry-with-backoff logic to `YouTubeClient.get_transcript()` for `youtube-transcript-api` 429 errors.
- Exponential backoff: 2s, 4s, 8s, 16s (4 retries max) before giving up on a video.
- Applies to both playlist and RSS transcript fetching.
- Configurable via `YOUTUBE_MAX_RETRIES` (default: 4) and `YOUTUBE_BACKOFF_BASE` (default: 2 seconds).

### Cloud OAuth Support
- Add `YOUTUBE_OAUTH_TOKEN_JSON` environment variable support for headless cloud deployments (Railway, Fly.io, etc.).
- On startup, if the token file doesn't exist but the env var is set, the token JSON is written to disk.
- The existing refresh logic handles token renewal without user interaction — refresh tokens are long-lived.
- Eliminates the need for volume mounts or interactive browser flows in cloud environments.
- OAuth is only needed for private playlists — public playlists work with API key alone.

## Impact

### Affected Specs
- `source-configuration` — new file-split convention, backoff, cloud OAuth, proofreading
- `cli-interface` — new subcommands for split ingestion

### Affected Code
- `sources.d/youtube.yaml` — split into two files
- `src/ingestion/youtube.py` — 429 backoff, cloud OAuth hydration, caption proofreading integration
- `src/ingestion/youtube_captions.py` — new module: LLM-based proofread function, hint terms loader, batch processing
- `src/config/sources.py` — `hint_terms` and `proofread` fields on `YouTubePlaylistSource`
- `src/config/models.py` — new `CAPTION_PROOFREADING` ModelStep
- `src/config/model_registry.yaml` — default model for caption proofreading
- `src/config/settings.py` — new settings (`youtube_max_retries`, `youtube_backoff_base`, `youtube_oauth_token_json`)
- `src/cli/ingest_commands.py` — new subcommands
- `src/cli/pipeline_commands.py` — split YouTube into two parallel ingestion tasks, add RSS feeds to pipeline
- `tests/test_ingestion/test_youtube.py` — backoff tests
- `tests/test_ingestion/test_youtube_captions.py` — proofread tests
- `tests/test_ingestion/test_youtube_rss.py` — config file path update

### Breaking Changes
- **None** — `aca ingest youtube` continues to work as before. The YAML split is transparent to `load_sources_directory` since it loads all `*.yaml` files. Existing automation calling `aca ingest youtube` is unaffected.
