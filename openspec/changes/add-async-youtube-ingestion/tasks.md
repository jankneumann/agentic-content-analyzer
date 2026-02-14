# Tasks: Add Async/Parallel YouTube Ingestion

## 1. Configuration

- [x] 1.1 Add `youtube_max_concurrent_videos: int = 5` to Settings class
- [x] 1.2 Add `youtube_max_concurrent_playlists: int = 3` to Settings class
- [x] 1.3 Update `src/config/settings.py` with new fields
- [x] 1.4 Add settings documentation in CLAUDE.md

## 2. KeyframeExtractor Async Conversion

### 2.1 Subprocess Operations
- [x] 2.1.1 Convert `_verify_ffmpeg()` to async using `asyncio.create_subprocess_exec()`
- [x] 2.1.2 Convert `get_video_duration()` to async subprocess call
- [x] 2.1.3 Convert `extract_scene_changes()` to async subprocess call
- [x] 2.1.4 Convert `extract_interval_frames()` to async subprocess call

### 2.2 Thread-Pooled Operations
- [x] 2.2.1 Convert `download_video()` to async using `asyncio.to_thread()` for yt-dlp
- [x] 2.2.2 Convert `compute_image_hash()` to async using `asyncio.to_thread()` for PIL/imagehash

### 2.3 Orchestration
- [x] 2.3.1 Convert `deduplicate_slides()` to use parallel hash computation via `asyncio.gather()`
- [x] 2.3.2 Convert `extract_unique_slides()` to async
- [x] 2.3.3 Convert `extract_keyframes_for_video()` to async orchestrator
- [x] 2.3.4 Update `is_available()` to async

## 3. YouTubeContentIngestionService Async Conversion

### 3.1 Core Methods
- [x] 3.1.1 Convert `ingest_playlist()` to async def
- [x] 3.1.2 Extract `_process_video()` as async helper method
- [x] 3.1.3 Convert `_extract_keyframes()` to async

### 3.2 Parallel Processing
- [x] 3.2.1 Implement parallel video processing with `asyncio.gather()`
- [x] 3.2.2 Add `asyncio.Semaphore` for video concurrency limiting
- [x] 3.2.3 Convert `ingest_all_playlists()` to async
- [x] 3.2.4 Add semaphore for playlist concurrency limiting

### 3.3 YouTube API Wrapping
- [x] 3.3.1 Wrap synchronous `get_playlist_videos()` with `asyncio.to_thread()`
- [x] 3.3.2 Wrap synchronous `get_transcript()` with `asyncio.to_thread()`

## 4. Transaction Isolation

- [x] 4.1 Refactor `_process_video()` to use its own `with get_db()` context
- [x] 4.2 Add error handling that captures failures without raising
- [x] 4.3 Use `return_exceptions=True` in `asyncio.gather()` for partial failure tracking
- [x] 4.4 Update `ingest_playlist()` to count successful results from gather
- [x] 4.5 Add logging for partial success scenarios

## 5. Entry Point Updates

- [x] 5.1 Update `main()` function to use `asyncio.run()`
- [x] 5.2 Update orchestrator `ingest_youtube_playlist()` with `asyncio.run()` bridge
- [x] 5.3 Update orchestrator `ingest_youtube_rss()` with `asyncio.run()` bridge
- [x] 5.4 Verify CLI/pipeline callers work unchanged (mock at orchestrator level)

## 6. Testing

### 6.1 Unit Tests
- [x] 6.1.1 Rewrite `KeyframeExtractor` tests to async (subprocess.run → asyncio.create_subprocess_exec)
- [x] 6.1.2 Rewrite `deduplicate_slides` test to async with AsyncMock
- [x] 6.1.3 Add async test for `YouTubeContentIngestionService.ingest_playlist()` empty case
- [x] 6.1.4 Add test for semaphore concurrency limiting (playlist and feed levels)

### 6.2 Integration Tests
- [x] 6.2.1 Add test for partial failure handling (one bad video in playlist)
- [x] 6.2.2 Update orchestrator tests to use AsyncMock for YouTube service methods
- [x] 6.2.3 Update CLI tests to mock asyncio.run() bridge

### 6.3 Performance Tests
- [ ] 6.3.1 Add benchmark comparing sequential vs parallel ingestion (deferred — requires live API)
- [ ] 6.3.2 Verify memory usage stays bounded with parallel downloads (deferred — requires live API)

## 7. Documentation

- [x] 7.1 Concurrency settings documented via Settings class defaults and CLAUDE.md
- [x] 7.2 Inline docstrings explaining async patterns added to service classes
- [ ] 7.3 Document concurrency best practices for YouTube API rate limits (deferred — follow-up)
- [ ] 7.4 Add architecture note about async subprocess usage (deferred — follow-up)
