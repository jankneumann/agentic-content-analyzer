# Change: Redesign YouTube Ingestion Pipeline (duration-routed Gemini processing)

**Change ID**: `redesign-youtube-ingestion-pipeline`
**Status**: Draft
**Created**: 2026-06-07

## Why

The current YouTube pipeline treats Gemini-native video and transcript fetching
as a **fallback chain** ("try Gemini → fall back to `youtube-transcript-api`")
rather than a deliberate, duration-aware **routing** strategy. This has three
concrete consequences:

1. **No length awareness.** Duration is only computed *after* the transcript is
   fetched (`src/ingestion/youtube.py:709`) and stored in metadata. There is no
   min/max length filter, and for the RSS path duration is not even known at
   filter time (the Atom feed carries no duration). We process 3-hour podcasts
   and 4-minute clips through the identical single Gemini call.

2. **Short-video processing is coarse.** The Gemini video call
   (`src/services/llm_router.py:1376` `_generate_gemini_with_video`) only tunes
   `media_resolution` (LOW/MED/HIGH). It does not control **frame sampling rate
   (`fps`)** and the extraction prompt does not request **timestamped segment
   boundaries + transcription** — the two capabilities called out in the Gemini
   video-understanding docs that make per-segment, citable output possible.

3. **Long videos have no viable strategy.** There is no >45-minute branch.
   Search grounding (`_generate_gemini_with_tools`, `llm_router.py:1461`) exists
   but is **orphaned** — nothing in YouTube ingestion calls it — and there is no
   file-segmentation path for very long videos that exceed practical
   single-call token/cost limits.

This change makes duration a first-class routing input and gives each length
class an appropriate processing strategy.

## What Changes

### Target pipeline (desired behavior)

1. **Discover** public-channel videos via RSS (existing) and playlists/channels
   (existing Data API path).
2. **Filter** candidate videos by topic *and* length (min/max duration) **before**
   any expensive processing.
3. **Route by duration:**
   - **3a — under threshold (default 45 min):** Gemini file-uri call with
     explicit `fps` (default ~`0.1`, i.e. 1 frame / 10 s) and a prompt that
     requests **timestamped segment boundaries + transcription**.
   - **3b — over threshold:** configurable per source —
     - `segments`: split into sub-threshold windows, run the 3a call per window
       (using `start_offset`/`end_offset` video metadata), stitch results; **or**
     - `grounding`: single configured-Google-model call with the URL in the
       prompt + Google Search grounding (no SDK video part) for a detailed
       summary. Default is `grounding`, with `segments` opt-in per source.

### New / changed components

1. **`src/services/llm_router.py`** — extend `generate_with_video` /
   `_generate_gemini_with_video` to accept `fps`, `start_offset`, `end_offset`
   and pass them via `types.VideoMetadata` on the video `Part`. Wire the existing
   grounding path for use by the long-video branch.
2. **`src/ingestion/youtube.py`** — replace the fallback chain in `_process_video`
   with a **duration router**; add a new extraction prompt requesting timestamped
   segments + transcription; add a segmentation helper for 3b.
3. **Duration probing** — obtain duration *at filter time*: Data API
   `videos().list(part="contentDetails")` for the playlist/channel path; a
   lightweight `yt-dlp`/oEmbed/Data-API probe for the RSS path.
4. **`src/config/sources.py`** — add length-filter and routing fields to the
   YouTube source models (see Spec Deltas).
5. **`sources.d/youtube_rss.yaml`, `youtube_playlist.yaml`, `_defaults.yaml`** —
   surface the new fields with sensible defaults.
6. **`settings/models.yaml`** — register the configured short-video model
   (`gemini-3.1-flash-lite` per request — **not currently in the registry**; add
   entry with capability flags + pricing, or alias to an existing Gemini model)
   and a `youtube_long_processing` step default.
7. **Tests** — unit tests for the router (fps/offsets, grounding), the duration
   router (boundary at threshold), the segmentation/stitch helper, and config
   parsing; regression coverage for short/long fixtures.

## Approaches Considered

### Duration source for the RSS path
- **A. Data API `contentDetails` lookup (selected default):** authoritative ISO-8601
  duration, one cheap quota unit per video. Cons: needs an API key for the RSS path
  (today RSS needs none).
- **B. `yt-dlp` metadata probe:** no API quota, but heavier dependency and more
  fragile/slow.
- **C. oEmbed:** does not return duration — rejected.
  Plan: default to A, allow B as a configurable fallback when no API key is set.

### Long-video strategy (3b)
Per decision: implement **both, configurable** — `grounding` (default) and
`segments` (opt-in). Grounding is cheap and needs no download; segments give
high fidelity at higher cost/complexity.

### Selected Approach (Gate 1)

Duration-routed processing with: Data API `contentDetails` as the primary
duration source and `yt-dlp` fallback; short path = Gemini file-uri with
`fps≈0.1` + timestamped-segment prompt; long path = configurable
`grounding` (default) / `segments` (opt-in). Model-registry freshness is
handled in a **separate change** (`auto-update-model-registry`) on this branch.

## Analysis: quality / cost / rate limits vs. current

Estimates use Gemini video tokenization (~258 tok/frame default res, ~66 low res,
**1 fps default sampling**, ~32 audio-tok/s) and registry prices
(`gemini-2.5-flash` $0.30/$2.50 per Mtok; `-flash-lite` $0.10/$0.40). Verify
constants against live Gemini docs at implementation time.

### Correctness cliff (most important)
At default 1 fps + medium res a video costs ~290 tok/s, so the 1M context window
is exhausted at **~57 min** (1e6 ÷ 290 ≈ 3448 s). **Videos beyond ~57 min are
truncated or fail today** — exactly the >45-min class. The redesign fixes this,
it is not merely an optimization.

### Cost (per video, input-dominated)
| Video | Current (1 fps) | Proposed short (fps 0.1, low) | Δ |
|---|---|---|---|
| 30 min | ~522k tok → $0.16 (flash) | ~70k tok → $0.021 / $0.007 lite | ~7.5× |
| 45 min | ~783k tok → $0.24 (flash) | ~104k tok → $0.031 / $0.010 lite | ~7.7× |
| 3 h | exceeds 1M → fails | routes to 3b | — |

3b @ 3 h: `grounding` ≈ $0.001–0.005 + grounding fees (summarizes *about* the
video, not true viewing); `segments` = 4 short calls ≈ $0.12 flash / $0.04 lite
(full fidelity, addressable). At ~600 videos/day: current ≈ $90–110/day (long
videos failing) → proposed ≈ $4–13/day with long videos succeeding.

### Quality
- Short path gains **timestamped segments + transcription** → citable/quotable,
  feeds the existing `&t=` deep-link affordance; output shape becomes predictable
  per video instead of varying with the Gemini/transcript fallback.
- Regression risk: fps 0.1 under-samples fast on-screen content (code/slides);
  mitigated by per-source `video_fps` override (keep 0.1 for AI-news, raise for
  demo/tutorial channels).

### Rate limits
- YouTube Data API: `videos.list(contentDetails)` batches 50 ids/unit → ~13
  units/day for all sources vs 10,000/day quota = negligible. RSS path newly uses
  quota only when an API key is present; `yt-dlp` fallback avoids it.
- Gemini TPM: fps 0.1 cuts per-video tokens ~5× → **relaxes** the binding TPM
  constraint. `segments` multiplies RPM → keep `youtube_max_concurrent_videos`.
- `yt-dlp`: no API quota but IP-throttle/bot-detection risk → API-first, yt-dlp
  fallback only.

## Impact

- **Behavior change:** processing path now depends on duration; output for short
  videos gains timestamped segments. Existing stored content is unaffected
  (re-ingest needed to adopt new format).
- **Cost:** filtering by length avoids processing out-of-scope videos; `fps`
  control reduces frame tokens for talking-head content. Long-video grounding is
  cheaper than today's full-video call; `segments` is more expensive (opt-in).
- **Config/quota:** RSS path may now consume Data API quota for duration probing.
- **No DB schema change** anticipated (duration already lives in `metadata_json`).
