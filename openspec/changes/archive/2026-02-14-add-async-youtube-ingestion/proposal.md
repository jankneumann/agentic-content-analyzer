# Change: Add Async/Parallel YouTube Ingestion

## Why

The current YouTube ingestion service processes videos **sequentially**, creating significant performance bottlenecks:

- A playlist with 50 videos takes ~25 minutes to ingest (30s/video when keyframe extraction is enabled)
- Blocking subprocess calls (ffmpeg for keyframe extraction) waste async event loop time
- Single transaction scope means one video failure loses all progress for the entire playlist
- Other ingestion services (files, images) already use async patterns, creating inconsistency

This change captures the async/parallel patterns from PR #44 (closed as architecturally outdated due to Newsletter→Content migration) and adapts them for the current unified Content model.

## What Changes

### Core Async Conversion
- Convert `YouTubeContentIngestionService.ingest_playlist()` to async
- Convert `YouTubeContentIngestionService.ingest_all_playlists()` to async
- Add `_process_video()` async helper for single video processing

### Parallel Processing
- Add parallel video processing within playlists via `asyncio.gather()`
- Add parallel playlist processing for multi-playlist ingestion
- Add configurable concurrency limits via new settings

### KeyframeExtractor Async Conversion
- Convert all blocking subprocess calls to `asyncio.create_subprocess_exec()`
- Wrap CPU-bound operations (yt-dlp, image hashing) with `asyncio.to_thread()`
- Add parallel hash computation for slide deduplication

### Failure Isolation
- Refactor to per-video database sessions (instead of single playlist transaction)
- Add partial success tracking with detailed error reporting
- One video failure no longer loses progress on other videos

### New Configuration Options
- `youtube_max_concurrent_videos` (default: 5) - Max parallel videos per playlist
- `youtube_max_concurrent_playlists` (default: 3) - Max parallel playlists

## Impact

### Affected Code
- `src/ingestion/youtube.py` - Service class async conversion
- `src/ingestion/youtube_keyframes.py` - Async subprocess and thread pools
- `src/config/settings.py` - New concurrency settings
- `tests/test_ingestion/test_youtube.py` - Async test patterns

### Performance
- Expected 5-10x speedup for playlist ingestion
- Non-blocking event loop during ffmpeg operations
- Better resource utilization through parallelism

### Breaking Changes
- **None** - The API remains the same; async conversion is internal
- Existing callers can continue using synchronous patterns via `asyncio.run()` wrapper

## Related Work

- **PR #44** (closed) - Original async/parallel implementation for Newsletter model
- **Files ingestion** (`src/ingestion/files.py`) - Reference implementation using async patterns
- **Image extraction** - Uses `asyncio` for concurrent HTTP downloads

## Current State

The YouTube ingestion pipeline currently:
1. Fetches playlist videos sequentially via YouTube Data API
2. Retrieves transcripts one at a time
3. Optionally extracts keyframes using blocking ffmpeg calls
4. Saves all content in a single database transaction
5. Fails entirely if any video encounters an error
