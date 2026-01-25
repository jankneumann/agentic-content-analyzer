# Design: Add Async/Parallel YouTube Ingestion

## Context

PR #44 implemented async/parallel YouTube ingestion but was closed as architecturally outdated—it used the deprecated Newsletter model instead of the unified Content model introduced during the data model migration.

The async patterns from PR #44 are valuable and should be preserved:
- `asyncio.gather()` for parallel video processing
- `asyncio.create_subprocess_exec()` for non-blocking ffmpeg calls
- `asyncio.to_thread()` for CPU-bound operations
- Per-video transaction isolation

This design adapts those patterns for the current Content model architecture.

## Goals

1. **5-10x performance improvement** for playlist ingestion through parallelism
2. **Failure isolation** so one video failure doesn't lose progress on others
3. **Configurable concurrency** to respect YouTube API rate limits
4. **Non-breaking change** - existing callers continue to work

## Non-Goals

- **Async YouTube API client** - Keep using google-api-python-client's sync wrapper; the overhead of wrapping in threads is acceptable
- **Distributed processing** - No multi-worker or Celery integration; single-process parallelism is sufficient
- **Real-time progress streaming** - Batch results returned at completion

---

## Decisions

### Decision 1: Parallel Execution via `asyncio.gather()` with Semaphore

**What:** Use `asyncio.gather()` to run video processing tasks concurrently, with `asyncio.Semaphore` to limit concurrent execution.

**Pattern:**
```python
async def ingest_playlist(self, playlist_id: str, max_videos: int = 10) -> IngestionResult:
    videos = await asyncio.to_thread(self.client.get_playlist_videos, playlist_id, max_videos)

    semaphore = asyncio.Semaphore(settings.youtube_max_concurrent_videos)

    async def process_with_limit(video):
        async with semaphore:
            return await self._process_video(video)

    tasks = [process_with_limit(video) for video in videos]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return IngestionResult.from_results(results)
```

**Rationale:**
- Simple pattern that matches existing codebase conventions
- No external dependencies (vs. aiohttp, anyio)
- Semaphore provides backpressure without complex queue management

**Alternatives Considered:**
- `ThreadPoolExecutor` with `loop.run_in_executor()` - Rejected; doesn't integrate cleanly with async/await, harder to compose
- `asyncio.TaskGroup` (Python 3.11+) - Could use, but `gather()` is more widely understood and we need exception handling control

---

### Decision 2: Per-Video Database Sessions

**What:** Each `_process_video()` call creates its own database session via `with get_db()`.

**Pattern:**
```python
async def _process_video(self, video: dict) -> VideoResult:
    try:
        with get_db() as db:
            # Check existence, create content, commit
            content = Content(...)
            db.add(content)
            db.commit()
            return VideoResult(success=True, content_id=content.id)
    except Exception as e:
        logger.error(f"Failed to process video {video['video_id']}: {e}")
        return VideoResult(success=False, error=str(e))
```

**Rationale:**
- Isolates failures - one video error doesn't rollback others
- Matches pattern used in other ingestion services
- SQLAlchemy connection pool handles concurrent session management

**Trade-off:** More connection overhead (one session per video vs. one per playlist). Acceptable at YouTube ingestion scale (typically 10-50 videos).

---

### Decision 3: `asyncio.to_thread()` for Blocking Libraries

**What:** Wrap synchronous library calls (yt-dlp, google-api-python-client, PIL/imagehash) in `asyncio.to_thread()`.

**Pattern:**
```python
async def download_video(self, video_id: str) -> str | None:
    def _download_sync():
        ydl_opts = {...}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://youtube.com/watch?v={video_id}"])
        return output_path

    return await asyncio.to_thread(_download_sync)
```

**Rationale:**
- yt-dlp has no async support; handles complex YouTube authentication and format selection
- google-api-python-client is synchronous; writing an async wrapper would be significant effort
- PIL/imagehash are CPU-bound; thread pool prevents blocking the event loop

**Alternatives Considered:**
- `aiohttp` for video downloads - Rejected; yt-dlp handles format negotiation, age restrictions, authentication that would require significant reimplementation
- `aiogoogle` for YouTube API - Rejected; less mature, would require migration effort

---

### Decision 4: Async Subprocess for ffmpeg

**What:** Replace `subprocess.run()` with `asyncio.create_subprocess_exec()` for all ffmpeg/ffprobe calls.

**Pattern:**
```python
async def get_video_duration(self, video_path: str) -> float:
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode()}")

    return float(stdout.decode().strip())
```

**Rationale:**
- ffmpeg operations can take 10-60 seconds per video
- Async subprocess allows event loop to process other videos during wait
- Maintains same command structure as current synchronous implementation

---

### Decision 5: Structured Result Type

**What:** Return `IngestionResult` dataclass instead of simple integer count.

**Pattern:**
```python
@dataclass
class VideoResult:
    video_id: str
    success: bool
    content_id: int | None = None
    error: str | None = None

@dataclass
class IngestionResult:
    total: int
    successful: int
    failed: int
    results: list[VideoResult]

    @classmethod
    def from_results(cls, results: list[VideoResult | Exception]) -> "IngestionResult":
        # Handle both VideoResult and exceptions from gather()
        ...
```

**Rationale:**
- Provides visibility into partial failures
- Enables retry logic for failed videos
- Better observability for monitoring/alerting

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| YouTube API rate limits | Quota exhaustion, temporary bans | Default concurrency of 5 videos; configurable via settings |
| Memory pressure from parallel downloads | OOM on large playlists | Temp files deleted immediately after processing; max 5 concurrent |
| Database connection exhaustion | Connection pool saturation | SQLAlchemy pool with default limits handles this; can configure pool_size if needed |
| Unhandled exceptions in gather() | Silent failures | Use `return_exceptions=True` and process all results |
| Race conditions in temp file cleanup | File conflicts | Use video_id in filename; atomic operations |

---

## Migration

**No migration required.** This is an internal implementation change:

- External API (`ingest_playlist()`, `ingest_all_playlists()`) remains the same
- Callers using sync patterns wrap with `asyncio.run()` (already standard in `main()`)
- Database schema unchanged
- Settings are additive (new fields with defaults)

---

## Open Questions

1. **Should we add retry logic for transient failures?**
   - Current: No retry, just report failure
   - Consider: Exponential backoff for rate limits

2. **Should progress be reported during ingestion?**
   - Current: Results returned at completion
   - Consider: Callback/webhook for progress updates

3. **Should we support cancellation?**
   - Current: No graceful cancellation
   - Consider: `asyncio.TaskGroup` with cancellation scope

---

## Implementation Notes

### File Changes Summary

| File | Change Type | Notes |
|------|-------------|-------|
| `src/ingestion/youtube.py` | Major refactor | Async methods, parallel processing, result types |
| `src/ingestion/youtube_keyframes.py` | Major refactor | Async subprocess, thread pools |
| `src/config/settings.py` | Minor addition | New concurrency settings |
| `tests/test_ingestion/test_youtube.py` | Moderate update | Async test patterns, new fixtures |

### Code Patterns Reference

**Async subprocess:**
```python
process = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
stdout, stderr = await process.communicate()
```

**Thread pool for sync code:**
```python
result = await asyncio.to_thread(sync_function, arg1, arg2)
```

**Semaphore-limited gather:**
```python
sem = asyncio.Semaphore(limit)
async def limited(coro):
    async with sem:
        return await coro
tasks = [limited(process(item)) for item in items]
results = await asyncio.gather(*tasks, return_exceptions=True)
```
