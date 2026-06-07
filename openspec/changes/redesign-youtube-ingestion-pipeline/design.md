# Design: Redesign YouTube Ingestion Pipeline

## Current vs. target architecture

### Current (fallback chain)

```
discover (RSS / Data API)
  └─ _process_video(video)
       ├─ if gemini_summary: _extract_video_content_with_gemini(url, resolution)   # single call, media_resolution only
       │     └─ router.generate_with_video → _generate_gemini_with_video → Part.from_uri(file_uri=url)
       └─ else / on failure: client.get_transcript → transcript_to_markdown        # 5s-gap paragraphing
  (duration computed AFTER, from transcript segments; no length filter)
```

Key current facts (verified):
- `src/services/llm_router.py:1376` — `_generate_gemini_with_video` sets only
  `media_resolution`; builds `types.Part.from_uri(file_uri=video_url, mime_type="video/mp4")`.
- `src/ingestion/youtube.py:547` — `_extract_video_content_with_gemini`; prompt at
  `:531` asks for prose, **no timestamps**.
- `src/ingestion/youtube.py:709` — `duration_seconds` computed post-hoc.
- `src/services/content_filter.py:47` — topic filter (`none` default), title+excerpt only.
- `src/services/llm_router.py:1461` — `_generate_gemini_with_tools` (grounding) exists, **unused** by YouTube.
- Model defaults: `settings/models.yaml:352` `youtube_processing: gemini-2.5-flash`,
  `youtube_rss_processing: gemini-2.5-flash-lite`.

### Target (duration router)

```
discover (RSS / Data API)
  └─ probe_duration(video)                     # NEW: Data API contentDetails | yt-dlp fallback
  └─ filter(topic, min_len, max_len)           # NEW length gate, BEFORE processing
  └─ route_by_duration(video, threshold=2700s):
       ├─ duration < threshold  → extract_short(url, fps, want_timestamps=True)
       │     └─ router.generate_with_video(fps=…, media_resolution=…)
       └─ duration >= threshold → long_strategy:
              ├─ "grounding" (default) → router.generate_with_grounding(prompt incl. url)
              └─ "segments" (opt-in)   → for window in split(duration, threshold):
                        extract_short(url, fps, start_offset, end_offset) ; stitch()
```

## Component-level changes

### 1. Router: fps + offsets + grounding wiring

`_generate_gemini_with_video` gains `fps: float | None`, `start_offset: str | None`,
`end_offset: str | None`. Build the video part with video metadata:

```python
# NOTE: verify exact shape against installed google-genai (pyproject: google-genai>=1.0.0).
# google not importable in this sandbox; confirm types.VideoMetadata fields at impl time.
video_part = types.Part(
    file_data=types.FileData(file_uri=video_url, mime_type="video/mp4"),
    video_metadata=types.VideoMetadata(
        fps=fps,                       # e.g. 0.1 == 1 frame / 10s
        start_offset=start_offset,     # e.g. "0s"
        end_offset=end_offset,         # e.g. "2700s"
    ),
)
```

`media_resolution` (existing) and `fps` (new) are **orthogonal**: resolution =
pixels/frame (token cost per frame), fps = frames/second (number of frames).
Default `fps≈0.1` is appropriate for talking-head/slide content; raise for
demo-heavy video.

Expose a thin `generate_with_grounding(...)` public method over the existing
`_generate_gemini_with_tools` so the long-video branch can call it without
reaching into a private method.

### 2. New short-video extraction prompt (timestamped segments + transcription)

Replace the prose-only `GEMINI_VIDEO_EXTRACTION_PROMPT` (for the short path) with
one that mandates per-segment structure, e.g.:

```
Analyze this video and produce timestamped segments. For each coherent segment:
- `## [HH:MM:SS – HH:MM:SS] <segment title>`
- A faithful transcription of what is said in that window
- Visuals/demos/code shown, and any on-screen text
Cover the entire video in order. Do not editorialize or summarize.
```

This yields citable, segment-addressable output (matching the fallback transcript
path's timestamp affordance, but from native video understanding).

### 3. Duration probing

- **Playlist/channel path:** add `videos().list(part="contentDetails")` batched by
  up to 50 ids; parse ISO-8601 `PT#H#M#S` → seconds. (Discovery already uses the
  Data API here.)
- **RSS path:** `probe_duration()` strategy ladder — Data API (if key present) →
  `yt-dlp --skip-download --print duration` fallback → if unknown, treat as
  "unknown" and route via a configurable `unknown_duration_strategy`
  (default: `short`, since most RSS channel uploads are short).

### 3.5 Credentials & auth (degradation matrix)

**Important:** a consumer "Google Pro / Gemini Advanced / AI Pro" subscription
grants no API access — inference always bills against an API key or GCP project.
Three independent credential axes affect this design:

| Axis | Code today | Options |
|---|---|---|
| Gemini inference | `_generate_gemini_with_video` → `genai.Client(api_key=GOOGLE_API_KEY)` (GOOGLE_AI only) | AI Studio key (free/paid) · Vertex (project+ADC) — **no Vertex video branch today** |
| YouTube discovery + duration | `YouTubeClient`, `videos.list(contentDetails)` | Data API key (public) · OAuth (private + user-project quota) |

Design rules:
- **AI Studio key is the default inference path.** Free tier has tight RPM/TPM →
  fps≈0.1 (lower TPM) and `grounding` long-default are the safe choices; paid tier
  unlocks `segments`.
- **Vertex is an optional inference branch** (`genai.Client(vertexai=True,
  project, location)`) — but **YouTube `file_uri` support on Vertex must be
  verified**; if unsupported, the short/segments paths fall back to grounding (or
  download→GCS) on Vertex. Treat Vertex video as out-of-scope until verified;
  document the fallback.
- **Duration-probe credential ladder:** OAuth (if configured) → Data API key →
  `yt-dlp` (no Google creds) → unknown→`unknown_duration_strategy`. OAuth vs key
  is interchangeable for `videos.list`; OAuth additionally unlocks private
  playlists (existing `visibility: private`).
- **Long-video default stays `grounding`** because it is the only path that works
  on the free tier AND survives a Vertex `file_uri` restriction.

### 4. Config schema (sources.d)

Add to `SourceDefaults` + YouTube source models (`src/config/sources.py`):

| Field | Type | Default | Meaning |
|---|---|---|---|
| `min_duration_seconds` | int \| None | None | drop videos shorter than this |
| `max_duration_seconds` | int \| None | None | drop videos longer than this |
| `long_video_threshold_seconds` | int | 2700 | 45-min routing boundary |
| `long_video_strategy` | `grounding` \| `segments` | `grounding` | 3b path |
| `video_fps` | float \| None | 0.1 | frame sampling for 3a |
| `segment_overlap_seconds` | int | 15 | overlap when `segments` |

Existing `gemini_resolution`, `gemini_summary`, `proofread`, `content_filter_*`
are retained.

### 5. Model registry

`gemini-3.1-flash-lite` (requested) is **absent** from `settings/models.yaml`
(present: `gemini-3-pro`, `gemini-3-flash`, `gemini-2.5-flash`,
`gemini-2.5-flash-lite`). Either:
- add a registry entry (capabilities: `supports_video: true`,
  `supports_audio: true`; pricing; context window), **or**
- alias the `youtube_processing` step to an existing model and document the intent.
Add a `youtube_long_processing` step default for the grounding/segment model.

## Control-flow boundary semantics

- Routing uses `>=` at the threshold: a video exactly at 2700 s goes to the long
  path. Documented and tested.
- Length **filter** (`min/max_duration_seconds`) is applied *before* routing and
  is independent of the routing threshold.

## Risks / open questions

1. **SDK surface for `fps`/offsets** — `google-genai>=1.0.0`; the exact
   `VideoMetadata` field names must be confirmed against the installed version at
   implementation time (sandbox cannot import `google`). Source-driven-development
   skill applies: fetch official docs + cite before coding.
2. **RSS quota** — duration probing may newly require a Data API key for RSS;
   `yt-dlp` fallback mitigates but adds a dependency. Confirm acceptable.
3. **Segment stitching quality** — overlapping windows can duplicate boundary
   content; stitch step must de-dupe by timestamp.
4. **Cost of `segments`** — opt-in only; document expected multiplier (≈ ceil(duration/threshold) calls).
5. **Grounding fidelity** — grounding summarizes *about* the URL; it does not do
   true frame/audio analysis. Acceptable for long-form per decision, but note the
   fidelity gap in user-facing docs.

## Test plan

- `tests/.../test_llm_router_video.py`: fps/offsets passed through; grounding
  method delegates correctly (mock genai client).
- `test_youtube_router.py`: boundary at threshold (2699/2700/2701 s); min/max
  filter drops correctly; unknown-duration routing.
- `test_youtube_segments.py`: window math + stitch de-dup.
- Config round-trip tests for new `sources.d` fields (defaults + override cascade).
- Regression: one short and one long fixture through `_process_video` with mocked router.
