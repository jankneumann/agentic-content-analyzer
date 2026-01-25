# Tasks: Add Async/Parallel YouTube Ingestion

## 1. Configuration

- [ ] 1.1 Add `youtube_max_concurrent_videos: int = 5` to Settings class
- [ ] 1.2 Add `youtube_max_concurrent_playlists: int = 3` to Settings class
- [ ] 1.3 Update `src/config/settings.py` with new fields
- [ ] 1.4 Add settings documentation in CLAUDE.md

## 2. KeyframeExtractor Async Conversion

### 2.1 Subprocess Operations
- [ ] 2.1.1 Convert `_verify_ffmpeg()` to async using `asyncio.create_subprocess_exec()`
- [ ] 2.1.2 Convert `get_video_duration()` to async subprocess call
- [ ] 2.1.3 Convert `extract_scene_changes()` to async subprocess call
- [ ] 2.1.4 Convert `extract_interval_frames()` to async subprocess call

### 2.2 Thread-Pooled Operations
- [ ] 2.2.1 Convert `download_video()` to async using `asyncio.to_thread()` for yt-dlp
- [ ] 2.2.2 Convert `compute_image_hash()` to async using `asyncio.to_thread()` for PIL/imagehash

### 2.3 Orchestration
- [ ] 2.3.1 Convert `deduplicate_slides()` to use parallel hash computation via `asyncio.gather()`
- [ ] 2.3.2 Convert `extract_unique_slides()` to async
- [ ] 2.3.3 Convert `extract_keyframes_for_video()` to async orchestrator
- [ ] 2.3.4 Update `is_available()` to async

## 3. YouTubeContentIngestionService Async Conversion

### 3.1 Core Methods
- [ ] 3.1.1 Convert `ingest_playlist()` to async def
- [ ] 3.1.2 Extract `_process_video()` as async helper method
- [ ] 3.1.3 Convert `_extract_keyframes()` to async

### 3.2 Parallel Processing
- [ ] 3.2.1 Implement parallel video processing with `asyncio.gather()`
- [ ] 3.2.2 Add `asyncio.Semaphore` for video concurrency limiting
- [ ] 3.2.3 Convert `ingest_all_playlists()` to async
- [ ] 3.2.4 Add semaphore for playlist concurrency limiting

### 3.3 YouTube API Wrapping
- [ ] 3.3.1 Wrap synchronous `get_playlist_videos()` with `asyncio.to_thread()` if needed
- [ ] 3.3.2 Wrap synchronous `get_transcript()` with `asyncio.to_thread()` if needed

## 4. Transaction Isolation

- [ ] 4.1 Refactor `_process_video()` to use its own `with get_db()` context
- [ ] 4.2 Add error handling that captures failures without raising
- [ ] 4.3 Create `IngestionResult` dataclass with success/failure tracking
- [ ] 4.4 Update `ingest_playlist()` return type to include detailed results
- [ ] 4.5 Add logging for partial success scenarios

## 5. Entry Point Updates

- [ ] 5.1 Update `main()` function to use `asyncio.run()`
- [ ] 5.2 Add `--max-concurrent-videos` CLI argument
- [ ] 5.3 Add `--max-concurrent-playlists` CLI argument
- [ ] 5.4 Ensure graceful shutdown on interrupt (cleanup temp files)

## 6. Testing

### 6.1 Unit Tests
- [ ] 6.1.1 Add async test for `KeyframeExtractor.download_video()`
- [ ] 6.1.2 Add async test for `KeyframeExtractor.extract_scene_changes()`
- [ ] 6.1.3 Add async test for `YouTubeContentIngestionService.ingest_playlist()`
- [ ] 6.1.4 Add test for semaphore concurrency limiting

### 6.2 Integration Tests
- [ ] 6.2.1 Add integration test for parallel video processing
- [ ] 6.2.2 Add test for partial failure handling (one bad video in playlist)
- [ ] 6.2.3 Add test verifying per-video transaction isolation

### 6.3 Performance Tests
- [ ] 6.3.1 Add benchmark comparing sequential vs parallel ingestion
- [ ] 6.3.2 Verify memory usage stays bounded with parallel downloads

## 7. Documentation

- [ ] 7.1 Update CLAUDE.md with new `youtube_max_concurrent_*` settings
- [ ] 7.2 Add inline docstrings explaining async patterns
- [ ] 7.3 Document concurrency best practices for YouTube API rate limits
- [ ] 7.4 Add architecture note about async subprocess usage
