## Context

YouTube transcript ingestion currently suffers from IP-based rate limiting when the `youtube-transcript-api` library scrapes transcripts for 60+ RSS channel feeds. The YouTube Data API provides an official `captions` endpoint (list + download) that uses quota-based rate limiting (10k units/day) instead of IP blocking, but requires OAuth credentials.

The system already has two separate services (`YouTubeContentIngestionService` for playlists, `YouTubeRSSIngestionService` for RSS feeds) that share a single config file and CLI command. This design formalizes the separation.

### Stakeholders
- Operators running daily ingestion pipelines
- Developers maintaining the ingestion codebase

## Goals / Non-Goals

- **Goals:**
  - Split source config so playlists and RSS feeds can be managed and scheduled independently
  - Use YouTube Data API captions for playlist videos when OAuth is available (avoids IP blocking)
  - Maintain backward compatibility — `aca ingest youtube` still works
  - Transparent to the `load_sources_directory` loader (no loader changes needed)

- **Non-Goals:**
  - Async/parallel ingestion (covered by separate proposal `add-async-youtube-ingestion`)
  - Rate-limit retry logic or backoff for youtube-transcript-api
  - Migrating RSS feeds to use the Data API (they have no playlists to discover from)
  - YouTube Data API quota management dashboard or alerts

## Decisions

### Decision 1: Split YAML files, not the loader

Split `youtube.yaml` into `youtube_playlist.yaml` and `youtube_rss.yaml`. The `load_sources_directory` function already loads all `*.yaml` files alphabetically and filters by source type via `get_youtube_playlist_sources()` / `get_youtube_rss_sources()`. No loader changes needed.

**Alternatives considered:**
- Add a `config_file` parameter to each service — rejected because it breaks the unified config model and requires service-level file path awareness.
- Use tags to distinguish playlist vs RSS within one file — rejected because it doesn't enable independent scheduling via separate CLI commands.

### Decision 2: YouTube Data API captions with fallback

Add `YouTubeClient.get_transcript_via_api(video_id, language)` that calls:
1. `captions.list(videoId=video_id)` — returns available tracks with IDs and language codes (50 quota units)
2. `captions.download(id=track_id, tfmt='srt')` — downloads the SRT-formatted captions (200 quota units)
3. Parse SRT into `TranscriptSegment` objects (reuse existing model)

The existing `get_transcript()` method gains a `prefer_data_api` parameter:
- `True` (default for playlist service): Try Data API first, fall back to youtube-transcript-api
- `False` (default for RSS service): Use youtube-transcript-api directly

**Why SRT format:** The `captions.download` endpoint supports `srt` and `sbv` formats via the `tfmt` parameter. SRT is widely supported and easy to parse into timed segments.

**Alternatives considered:**
- Always use Data API for all sources — rejected because `captions.download` requires OAuth, and RSS feed videos are from channels the operator doesn't own.
- Use `captions.list` to check availability then youtube-transcript-api to download — rejected because the rate-limiting occurs during the transcript fetch, not the listing.

### Decision 3: Separate CLI subcommands with combined fallback

```
aca ingest youtube-playlist  # Only playlists/channels from youtube_playlist.yaml
aca ingest youtube-rss       # Only RSS feeds from youtube_rss.yaml
aca ingest youtube            # Both (backward compatible)
```

The combined command creates both services and runs them sequentially, matching current behavior.

**Alternatives considered:**
- Replace `aca ingest youtube` with the two new commands — rejected for backward compatibility.
- Add `--source-type playlist|rss` flag — rejected because separate commands are clearer for cron scheduling.

### Decision 4: OAuth required for Data API captions

The `captions.download` endpoint requires OAuth with `youtube.force-ssl` scope. This is already configured for private playlist access. When OAuth is unavailable (API key only), playlist ingestion falls back to youtube-transcript-api — same as today.

This means the full rate-limit benefit only applies when OAuth is configured, which is the expected production setup for operators who manage their own playlists.

### Decision 5: Caption proofreading with static dictionary + optional LLM

Auto-generated YouTube captions frequently misspell proper nouns phonetically (e.g., "clawd" or "cloud" instead of "Claude"). A proofread step corrects these after transcript retrieval, before markdown conversion.

**Static dictionary approach:**
- Case-insensitive whole-word replacement using a corrections map
- Built-in defaults for common AI terms (`{"clawd": "Claude", "open eye": "OpenAI", "lama": "LLaMA", "chet gpt": "ChatGPT"}`)
- Per-playlist overrides in YAML config
- Only applied to auto-generated captions (manual captions are assumed correct)

**Alternatives considered:**
- LLM-based proofread for every transcript — rejected for initial implementation due to cost and latency. Can be added as a future enhancement for ambiguous cases (e.g., "cloud" could be correct in a cloud computing context).
- Regex-based corrections — rejected because whole-word replacement is simpler and covers the common cases without regex complexity.

## Risks / Trade-offs

- **Quota consumption**: At 250 units/video, operators can process ~40 playlist videos/day via Data API. This is sufficient for the current 2 playlists but may need monitoring if playlists grow. → Mitigation: Log quota usage, add `YOUTUBE_PREFER_DATA_API_CAPTIONS` toggle.

- **OAuth scope**: `captions.download` may fail for videos not owned by the OAuth user. → Mitigation: Fall back to youtube-transcript-api per video, not per playlist.

- **SRT parsing**: New parsing code for SRT format. → Mitigation: SRT is a simple, well-defined format. Parser is ~30 lines.

- **Proofread false positives**: Static dictionary may incorrectly replace legitimate words (e.g., "cloud" in a cloud computing context). → Mitigation: Only apply to auto-generated captions; per-playlist overrides allow disabling or customizing corrections; `proofread: false` opt-out.

## Migration Plan

1. Create `youtube_playlist.yaml` and `youtube_rss.yaml` from existing `youtube.yaml` entries.
2. Remove `youtube.yaml`.
3. No database migration needed — Content records are unchanged.
4. No API migration — existing `aca ingest youtube` continues working.

**Rollback:** Recombine the two YAML files into `youtube.yaml`. Remove the new CLI commands. Revert `get_transcript()` changes.

## Open Questions

1. Should `captions.download` failures for non-owned videos be logged at `WARNING` or `DEBUG` level? (Proposal: `DEBUG` since fallback is expected behavior.)
2. Should quota usage be tracked in a persistent counter or just logged? (Proposal: just logged — YouTube API itself enforces the quota.)
