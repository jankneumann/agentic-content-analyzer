# YouTube Ingestion Spec Delta

## ADDED Requirements

### Requirement: Parallel Video Processing

The system SHALL process multiple videos from a playlist concurrently to improve ingestion throughput.

#### Scenario: Concurrent video processing within playlist
- **GIVEN** a YouTube playlist with 10 videos
- **WHEN** the playlist is ingested with `youtube_max_concurrent_videos=5`
- **THEN** up to 5 videos SHALL be processed simultaneously
- **AND** the total ingestion time SHALL be significantly less than sequential processing

#### Scenario: Concurrency respects configured limit
- **GIVEN** `youtube_max_concurrent_videos` is set to 3
- **WHEN** processing a playlist with 10 videos
- **THEN** at most 3 videos SHALL be downloading/processing at any given time

### Requirement: Parallel Playlist Processing

The system SHALL process multiple playlists concurrently when ingesting from multiple sources.

#### Scenario: Concurrent playlist processing
- **GIVEN** 3 configured YouTube playlists
- **WHEN** `ingest_all_playlists()` is called with `youtube_max_concurrent_playlists=2`
- **THEN** up to 2 playlists SHALL be processed simultaneously

### Requirement: Per-Video Failure Isolation

The system SHALL isolate failures to individual videos, allowing partial playlist ingestion success.

#### Scenario: Single video failure does not affect others
- **GIVEN** a playlist with 10 videos where video #5 has an invalid transcript
- **WHEN** the playlist is ingested
- **THEN** videos 1-4 and 6-10 SHALL be successfully ingested
- **AND** video #5 SHALL be reported as failed in the results
- **AND** the ingestion SHALL return a partial success result

#### Scenario: Detailed failure reporting
- **GIVEN** a playlist ingestion where 2 videos fail
- **WHEN** the ingestion completes
- **THEN** the result SHALL include total count, success count, and failure count
- **AND** the result SHALL include error details for each failed video

### Requirement: Configurable Concurrency Limits

The system SHALL allow configuration of concurrency limits to respect API rate limits and resource constraints.

#### Scenario: Video concurrency setting
- **GIVEN** the setting `youtube_max_concurrent_videos` exists
- **WHEN** set to a positive integer
- **THEN** video processing concurrency SHALL be limited to that value
- **AND** the default value SHALL be 5

#### Scenario: Playlist concurrency setting
- **GIVEN** the setting `youtube_max_concurrent_playlists` exists
- **WHEN** set to a positive integer
- **THEN** playlist processing concurrency SHALL be limited to that value
- **AND** the default value SHALL be 3

### Requirement: Non-Blocking Keyframe Extraction

The system SHALL perform keyframe extraction without blocking the async event loop.

#### Scenario: Async ffmpeg operations
- **GIVEN** keyframe extraction is enabled
- **WHEN** extracting frames from a video
- **THEN** ffmpeg subprocess calls SHALL be non-blocking
- **AND** other videos SHALL continue processing during ffmpeg execution

#### Scenario: Async video download
- **GIVEN** keyframe extraction requires video download
- **WHEN** downloading a video via yt-dlp
- **THEN** the download SHALL run in a separate thread
- **AND** the async event loop SHALL not be blocked
