## Context

YouTube transcript ingestion currently suffers from IP-based rate limiting when the `youtube-transcript-api` library scrapes transcripts for 60+ RSS channel feeds. Both the playlist service and RSS service use this library, and because they share a single config file and CLI command, they cannot be run independently. A rate-limit failure during RSS ingestion blocks the higher-priority playlist ingestion.

The system already has two separate services (`YouTubeContentIngestionService` for playlists, `YouTubeRSSIngestionService` for RSS feeds) — this design formalizes the separation at the config and CLI level.

### Stakeholders
- Operators running daily ingestion pipelines
- Developers maintaining the ingestion codebase

## Goals / Non-Goals

- **Goals:**
  - Split source config so playlists and RSS feeds can be managed and scheduled independently
  - Prioritize playlist ingestion (curated, fewer videos) over RSS feeds (60+ channels, bulk)
  - Add exponential backoff on 429 errors to handle transient rate limits gracefully
  - Support OAuth token deployment in headless cloud environments (Railway, Fly.io)
  - Correct phonetic misspellings in auto-generated captions
  - Maintain backward compatibility — `aca ingest youtube` still works

- **Non-Goals:**
  - YouTube Data API captions endpoint (requires video ownership for `captions.download`)
  - Async/parallel ingestion (covered by separate proposal `add-async-youtube-ingestion`)
  - Global rate limiter or token bucket for youtube-transcript-api
  - YouTube Data API quota management dashboard or alerts

## Decisions

### Decision 1: Split YAML files, not the loader

Split `youtube.yaml` into `youtube_playlist.yaml` and `youtube_rss.yaml`. The `load_sources_directory` function already loads all `*.yaml` files alphabetically and filters by source type via `get_youtube_playlist_sources()` / `get_youtube_rss_sources()`. No loader changes needed.

**Alternatives considered:**
- Add a `config_file` parameter to each service — rejected because it breaks the unified config model and requires service-level file path awareness.
- Use tags to distinguish playlist vs RSS within one file — rejected because it doesn't enable independent scheduling via separate CLI commands.

### Decision 2: Separate CLI subcommands with combined fallback

```
aca ingest youtube-playlist  # Only playlists/channels from youtube_playlist.yaml
aca ingest youtube-rss       # Only RSS feeds from youtube_rss.yaml
aca ingest youtube            # Both (backward compatible)
```

The combined command creates both services and runs them sequentially (playlists first), matching current behavior.

**Alternatives considered:**
- Replace `aca ingest youtube` with the two new commands — rejected for backward compatibility.
- Add `--source-type playlist|rss` flag — rejected because separate commands are clearer for cron scheduling.

### Decision 2b: Pipeline ingestion stage split

The `aca pipeline daily/weekly` commands run ingestion via `_run_ingestion_stage_async()` which uses `asyncio.gather()` to run sources in parallel. Currently YouTube is a single task that only calls `ingest_all_playlists()` — **YouTube RSS feeds are not included in the pipeline at all**.

Update to run `youtube-playlist` and `youtube-rss` as two separate parallel tasks alongside the other sources (Gmail, RSS, Podcast, Substack). This changes the parallel task count from 5 to 6.

```python
# Before (5 tasks, RSS feeds missing)
tasks = [
    _ingest_source("gmail", ...),
    _ingest_source("rss", ...),
    _ingest_source("youtube", youtube_service.ingest_all_playlists),
    _ingest_source("podcast", ...),
    _ingest_source("substack", ...),
]

# After (6 tasks, RSS feeds included)
tasks = [
    _ingest_source("gmail", ...),
    _ingest_source("rss", ...),
    _ingest_source("youtube-playlist", youtube_service.ingest_all_playlists),
    _ingest_source("youtube-rss", rss_service.ingest_all_feeds),
    _ingest_source("podcast", ...),
    _ingest_source("substack", ...),
]
```

**Why not keep a single "youtube" task:** The whole point is independent execution. If `youtube-rss` hits rate limits, `youtube-playlist` completes independently. The pipeline already handles per-source failures via the `_ingest_source` wrapper.

### Decision 3: Caption proofreading with static dictionary

Auto-generated YouTube captions frequently misspell proper nouns phonetically (e.g., "clawd" or "cloud" instead of "Claude"). A proofread step corrects these after transcript retrieval, before markdown conversion.

**Static dictionary approach:**
- Case-insensitive whole-word replacement using a corrections map
- Built-in defaults for common AI terms (`{"clawd": "Claude", "open eye": "OpenAI", "lama": "LLaMA", "chet gpt": "ChatGPT"}`)
- Per-playlist overrides in YAML config
- Only applied to auto-generated captions (manual captions are assumed correct)

**Alternatives considered:**
- LLM-based proofread for every transcript — rejected for initial implementation due to cost and latency. Can be added as a future enhancement for ambiguous cases (e.g., "cloud" could be correct in a cloud computing context).
- Regex-based corrections — rejected because whole-word replacement is simpler and covers the common cases without regex complexity.

### Decision 4: Exponential backoff on 429 rate limiting

The `youtube-transcript-api` scrapes YouTube for transcripts and can trigger HTTP 429 (Too Many Requests) responses. The system SHALL retry with exponential backoff before giving up on a video.

**Backoff strategy:**
- Base delay: 2 seconds (configurable via `YOUTUBE_BACKOFF_BASE`)
- Max retries: 4 (configurable via `YOUTUBE_MAX_RETRIES`)
- Progression: 2s → 4s → 8s → 16s (total wait: 30s before failure)
- Per-video scope: a failure after retries skips that video, doesn't abort the playlist/feed
- Jitter: add ±20% random jitter to avoid thundering herd when multiple feeds retry simultaneously

**Implementation:** Simple inline retry loop to avoid adding a dependency purely for retry logic.

**Alternatives considered:**
- Global rate limiter (token bucket) — rejected as over-engineering for the current scale. The backoff handles the common case where YouTube returns 429 after a burst of requests.
- Circuit breaker pattern — rejected because the ingestion is batch-oriented (not continuous), so a circuit breaker adds complexity without clear benefit.

### Decision 5: Cloud OAuth via environment variable

Cloud deployments (Railway, Fly.io) cannot run `InstalledAppFlow.run_local_server()` (requires a browser). Instead, operators generate the OAuth token locally once and deploy it as an environment variable.

Note: OAuth is only needed for **private playlists**. Public playlists and all RSS feeds work with just a `GOOGLE_API_KEY` or no API key at all (RSS feeds use feedparser, not the YouTube Data API).

**Flow:**
1. Operator runs `aca ingest youtube` locally — triggers OAuth browser flow, creates `youtube_token.json`
2. Operator copies the token JSON content into `YOUTUBE_OAUTH_TOKEN_JSON` env var in Railway/Fly.io
3. On cloud startup, `_authenticate_oauth()` checks for the env var and hydrates the token file before loading credentials
4. The existing refresh logic auto-renews the access token using the refresh token — no browser needed

**Why env var over volume mount:**
- Stateless deploys (no volume dependency)
- Works on all cloud providers (Railway, Fly.io, Render, etc.)
- Refresh tokens are long-lived (don't expire unless explicitly revoked in Google Cloud Console)
- Compatible with Railway's secret management and `railway_env_sync.py`

**Token refresh in cloud:**
- Access tokens expire after 1 hour
- The existing `creds.refresh(Request())` call auto-refreshes using the refresh token
- The refreshed token is saved back to the file (which is ephemeral in cloud, but that's fine — the env var provides the refresh token for the next deploy)

## Risks / Trade-offs

- **Backoff delays**: 4 retries with exponential backoff adds up to 30s per video worst-case. For 60+ RSS feeds, this could extend total ingestion time. → Mitigation: Backoff only triggers on 429s (not common for every video); per-video scope means other videos proceed normally.

- **Proofread false positives**: Static dictionary may incorrectly replace legitimate words (e.g., "cloud" in a cloud computing context). → Mitigation: Only apply to auto-generated captions; per-playlist overrides allow disabling or customizing corrections; `proofread: false` opt-out.

- **Cloud token expiry**: If the refresh token is revoked in Google Cloud Console, cloud deployments lose OAuth until the operator re-generates the token locally. → Mitigation: Log a clear error message with instructions when refresh fails.

## Migration Plan

1. Create `youtube_playlist.yaml` and `youtube_rss.yaml` from existing `youtube.yaml` entries.
2. Remove `youtube.yaml`.
3. No database migration needed — Content records are unchanged.
4. No API migration — existing `aca ingest youtube` continues working.

**Rollback:** Recombine the two YAML files into `youtube.yaml`. Remove the new CLI commands.

## Open Questions

1. Should the combined `aca ingest youtube` command run playlists first, then RSS? (Proposal: yes — playlists are higher priority and have fewer videos, so they complete before any RSS rate limiting kicks in.)
2. Should there be a configurable delay between playlist and RSS ingestion in the combined command? (Proposal: no — keep it simple; operators who want a gap should use separate cron jobs.)
