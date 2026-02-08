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
  - Use Gemini native YouTube video summarization to bypass `youtube-transcript-api` rate limiting
  - Differentiate model quality: stronger model for curated playlists, cheapest for bulk RSS
  - Use lowest resolution (`media_resolution: LOW`) for RSS to minimize cost
  - Add exponential backoff on 429 errors for transcript-based fallback flow
  - Support OAuth token deployment in headless cloud environments (Railway, Fly.io)
  - Correct phonetic misspellings in auto-generated captions (transcript-based flow)
  - Maintain backward compatibility — `aca ingest youtube` still works

- **Non-Goals:**
  - YouTube Data API captions endpoint (requires video ownership for `captions.download`)
  - Async/parallel ingestion (covered by separate proposal `add-async-youtube-ingestion`)
  - Global rate limiter or token bucket for youtube-transcript-api
  - Gemini processing of private/unlisted videos (public only; auto-fallback to transcript)

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

### Decision 3: LLM-based caption proofreading

Auto-generated YouTube captions frequently misspell proper nouns phonetically (e.g., "clawd" or "cloud" instead of "Claude"). A static dictionary can't handle these reliably because many misspellings are also real words ("cloud" is legitimate in cloud computing context, "lama" is a real animal). Contextual understanding is required.

**LLM-based approach:**
- Use a fast, cheap model (default: `gemini-2.5-flash-lite` or `claude-haiku-4-5`) to proofread transcript segments
- Add `CAPTION_PROOFREADING` as a new `ModelStep` in `src/config/models.py` with env var `MODEL_CAPTION_PROOFREADING`
- Send transcript text in batches (e.g., 50 segments at a time) with a system prompt containing:
  - A hint list of commonly misspelled terms specific to AI/tech domain (configurable per-playlist via YAML `hint_terms`)
  - Instructions to only correct proper noun misspellings, preserving all other text exactly
  - The domain context (AI/ML newsletter content) to disambiguate
- Return corrected text in the same segment structure (preserving timestamps)
- Only applied to auto-generated captions (manual captions skipped)
- Gated by `proofread: true` (default) per playlist source — can be disabled

**Batching strategy:**
- Group segments into batches of ~50 to stay well within context limits
- Each batch is a single LLM call with all segments numbered for alignment
- The prompt asks the LLM to return only changed segments (sparse diff) to minimize output tokens
- Estimated cost: ~$0.001-0.005 per video transcript with flash-lite models

**Hint terms (configurable):**
```yaml
# youtube_playlist.yaml
defaults:
  hint_terms:
    - Claude
    - Anthropic
    - OpenAI
    - LLaMA
    - ChatGPT
    - Gemini
    - Mistral

sources:
  - type: youtube_playlist
    id: PLN4UY0S3lPrs40eHdRIiJ-iXJYMkjI4P6
    name: Nate's Newsletter Playlist
    proofread: true
    hint_terms:  # Per-playlist additions merged with defaults
      - Comcast
      - Xfinity
```

**Alternatives considered:**
- Static dictionary only — rejected because context-dependent corrections (e.g., "cloud" vs "Claude") require understanding the surrounding text. A dictionary would either miss real misspellings or create false positives.
- Full LLM rewrite of transcripts — rejected because we want minimal changes (only proper noun corrections), not paraphrasing. The prompt explicitly constrains the LLM to only fix misspellings.
- Heavier model (Sonnet) — rejected because proofreading is a simple classification/correction task. Flash-lite models handle it well at 10-50x lower cost.

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

### Decision 6: Gemini native YouTube video summarization

Instead of fetching transcripts via `youtube-transcript-api` (which scrapes YouTube and triggers IP blocks), use Gemini's native YouTube URL support to generate structured summaries directly from the video. Gemini processes the video internally — audio + visual — via `Part.from_uri(file_uri="https://www.youtube.com/watch?v=...", mime_type="video/mp4")`.

This is a **combined ingest+summarize step**: Gemini's output IS the structured summary. No transcript fetch, no separate summarization pass, no rate-limiting from scraping.

**Two-tier model configuration:**

| Path | Default Model | Resolution | Rationale |
|------|--------------|------------|-----------|
| Playlists | `gemini-2.5-flash` (`YOUTUBE_PROCESSING`) | default (258 tok/frame) | Curated, higher quality wanted |
| RSS feeds | `gemini-2.5-flash-lite` (`YOUTUBE_RSS_PROCESSING`) | LOW (66 tok/frame, ~3x cheaper) | Bulk, cost-sensitive |

**Resolution control via `media_resolution` parameter:**
- `LOW`: 66 tokens/frame — 3x cheaper than default, sufficient for summary extraction
- Default: 258 tokens/frame — better for detailed analysis of curated content
- Configurable per-source via `gemini_resolution: low | medium | high | default`

**LLM router extension:**
- New `generate_with_video(model, system_prompt, user_prompt, video_url, media_resolution)` method on the Gemini backend
- Uses `Part.from_uri(file_uri=url, mime_type="video/mp4")` alongside text prompt
- Prompt requests structured summary matching the digest pipeline's expectations (key topics, insights, technical details, relevance scores)

**Source configuration:**
```yaml
# youtube_playlist.yaml
defaults:
  gemini_summary: true          # Use Gemini native video summarization
  gemini_resolution: default    # Higher quality for curated playlists

sources:
  - type: youtube_playlist
    id: PLxxx
    name: Curated AI Playlist
    gemini_summary: true

# youtube_rss.yaml
defaults:
  gemini_summary: true
  gemini_resolution: low        # Lowest cost for bulk RSS

sources:
  - type: youtube_rss
    url: https://...
    gemini_summary: true
```

**Content storage:**
- Stored as `ContentSource.YOUTUBE` (same as now)
- Content field contains the Gemini-generated structured summary (not a raw transcript)
- `metadata_json` includes `"processing_method": "gemini_native"`, model used, and resolution
- Summarization step detects `processing_method: gemini_native` and skips re-summarization (content is already a summary)

**Fallback to transcript-based flow:**
- If `GOOGLE_API_KEY` is not set → fall back to `youtube-transcript-api`
- If Gemini returns an error for a specific video (e.g., private/unlisted video) → fall back per-video
- If `gemini_summary: false` per-source → use transcript-based flow
- Private playlists: OAuth lists video IDs, then Gemini summarizes public videos within the playlist. Truly private videos fall back to transcript-based.

**Public-only limitation:**
Gemini native video processing only works for public YouTube videos. Videos within a private playlist are typically public (the playlist is private, not the videos). For truly private/unlisted videos that Gemini can't access, the system falls back to transcript-based processing automatically.

**Alternatives considered:**
- Use Gemini for transcript extraction only (not summarization) — rejected because the summarization step adds cost and latency for no benefit when Gemini can produce the summary directly.
- Single model for both playlist and RSS — rejected because the user wants differentiated quality. Curated playlists deserve a stronger model; bulk RSS feeds prioritize cost.
- Upload video via File API instead of URL — rejected because `Part.from_uri` with YouTube URLs avoids download/upload overhead and is the intended pattern for YouTube content.

## Risks / Trade-offs

- **Backoff delays**: 4 retries with exponential backoff adds up to 30s per video worst-case. For 60+ RSS feeds, this could extend total ingestion time. → Mitigation: Backoff only triggers on 429s (not common for every video); per-video scope means other videos proceed normally.

- **Proofread cost**: LLM calls add cost per video (~$0.001-0.005 with flash-lite). For 40+ videos/day this is negligible ($0.04-0.20/day). → Mitigation: Use cheapest model (gemini-2.5-flash-lite); configurable via `MODEL_CAPTION_PROOFREADING`; `proofread: false` opt-out per playlist.

- **Proofread latency**: LLM batching adds ~1-3 seconds per video. → Mitigation: Batch 50 segments per call to minimize round-trips; runs after transcript fetch which is already the slow path.

- **Proofread hallucinations**: LLM might over-correct or change non-misspelled text. → Mitigation: Prompt explicitly constrains corrections to proper nouns only; sparse-diff output format means unchanged segments are preserved exactly; hint terms guide the LLM toward expected corrections.

- **Cloud token expiry**: If the refresh token is revoked in Google Cloud Console, cloud deployments lose OAuth until the operator re-generates the token locally. → Mitigation: Log a clear error message with instructions when refresh fails.

- **Gemini native: public videos only**: Gemini can only access public YouTube videos via URL. Truly private/unlisted videos won't work. → Mitigation: Auto-fallback to transcript-based flow per-video; most videos in private playlists are publicly accessible (the playlist is private, not the videos).

- **Gemini native: summary vs transcript fidelity**: Gemini produces a summary, not a verbatim transcript. Exact quotes and timestamps are not preserved. → Mitigation: Acceptable trade-off for the digest pipeline which summarizes content anyway. If exact quotes are needed, operator sets `gemini_summary: false` per-source to use transcript flow.

- **Gemini native: cost at scale for RSS**: Even with `media_resolution: LOW` and flash-lite, processing 60+ RSS channels with many videos daily could accumulate cost. → Mitigation: `max_entries` per source limits video count; operator can set `gemini_summary: false` for low-priority RSS feeds; cost is still lower than IP blocks that prevent any ingestion.

- **Gemini 2.0 Flash retirement**: Gemini 2.0 Flash and Flash-Lite retire March 31, 2026. → Mitigation: Default models use 2.5-series; model registry makes switching trivial via config.

## Migration Plan

1. Create `youtube_playlist.yaml` and `youtube_rss.yaml` from existing `youtube.yaml` entries.
2. Remove `youtube.yaml`.
3. No database migration needed — Content records are unchanged.
4. No API migration — existing `aca ingest youtube` continues working.

**Rollback:** Recombine the two YAML files into `youtube.yaml`. Remove the new CLI commands.

## Open Questions

1. Should the combined `aca ingest youtube` command run playlists first, then RSS? (Proposal: yes — playlists are higher priority and have fewer videos, so they complete before any RSS rate limiting kicks in.)
2. Should there be a configurable delay between playlist and RSS ingestion in the combined command? (Proposal: no — keep it simple; operators who want a gap should use separate cron jobs.)
