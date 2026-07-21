# youtube-ingestion Specification

## Purpose
TBD - created by archiving change add-async-youtube-ingestion. Update Purpose after archive.
## Requirements
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

### Requirement: Length filtering before processing

The system SHALL filter discovered YouTube videos by duration before invoking any
Gemini or transcript processing, independently of topic filtering.

#### Scenario: Length filter drops out-of-range videos
- **GIVEN** a YouTube source with `min_duration_seconds=120` and `max_duration_seconds=7200`
- **WHEN** a discovered video with duration 30s is evaluated
- **THEN** the video SHALL be skipped before any Gemini/transcript call
- **AND** a video with duration 600s SHALL pass the length filter

#### Scenario: Topic filter applies independently of length
- **GIVEN** a source with `content_filter_strategy="keyword"` and length filters set
- **WHEN** a video passes the length filter but fails the topic filter
- **THEN** the video SHALL be skipped and no processing call SHALL be made

### Requirement: Duration probing

The system SHALL resolve each candidate video's duration before routing.

#### Scenario: Duration probed on playlist/channel path
- **GIVEN** the Data API playlist/channel discovery path
- **WHEN** videos are discovered
- **THEN** `videos().list(part="contentDetails")` SHALL be used to resolve duration
- **AND** ISO-8601 `PT#H#M#S` durations SHALL be parsed to seconds

#### Scenario: Duration probed on RSS path with fallback
- **GIVEN** the RSS discovery path
- **WHEN** a video is discovered and an API key is available
- **THEN** duration SHALL be probed via the Data API
- **AND** if no API key is available, a `yt-dlp` metadata probe SHALL be attempted
- **AND** if duration remains unknown, routing SHALL use `unknown_duration_strategy` (default `short`)

### Requirement: Duration-based routing

The system SHALL route videos to a processing strategy based on duration relative
to `long_video_threshold_seconds`.

#### Scenario: Short videos use Gemini file-uri with fps and timestamps
- **GIVEN** `long_video_threshold_seconds=2700` and a 600s video
- **WHEN** the video is routed
- **THEN** `generate_with_video` SHALL be called with the YouTube URL as a file-uri part
- **AND** `fps` SHALL be passed (default `0.1`) via video metadata
- **AND** the extraction prompt SHALL request timestamped segment boundaries and transcription

#### Scenario: Threshold boundary is inclusive toward the long path
- **GIVEN** `long_video_threshold_seconds=2700`
- **WHEN** a video of exactly 2700s is routed
- **THEN** it SHALL take the long-video path (routing uses `>=`)
- **AND** a 2699s video SHALL take the short path

#### Scenario: Long videos default to grounding strategy
- **GIVEN** a source with `long_video_strategy` unset and a 5400s video
- **WHEN** the video is routed
- **THEN** a single configured-Google-model call SHALL be made with the URL in the prompt and Google Search grounding
- **AND** no SDK video file-uri part SHALL be attached

#### Scenario: Long videos with segments strategy split and stitch
- **GIVEN** a source with `long_video_strategy="segments"`, threshold 2700s, and a 6000s video
- **WHEN** the video is routed
- **THEN** the video SHALL be split into windows of at most 2700s with `segment_overlap_seconds` overlap
- **AND** each window SHALL be processed via the Gemini file-uri call using `start_offset`/`end_offset`
- **AND** results SHALL be stitched with boundary de-duplication by timestamp

### Requirement: Configuration surface

The system SHALL expose duration-filter and routing settings via source config
with documented defaults and the standard override cascade.

#### Scenario: New source fields parse with defaults
- **GIVEN** a `sources.d/youtube_rss.yaml` entry omitting the new fields
- **WHEN** sources are loaded
- **THEN** `long_video_threshold_seconds` SHALL default to 2700
- **AND** `long_video_strategy` SHALL default to `grounding`
- **AND** `video_fps` SHALL default to 0.1
- **AND** per-source overrides SHALL take precedence over file defaults over `_defaults.yaml`

#### Scenario: Short-video model resolvable from registry
- **GIVEN** the `youtube_processing` model step configured to the short-video model
- **WHEN** `get_model_for_step(ModelStep.YOUTUBE_PROCESSING)` is called
- **THEN** the returned model id SHALL exist in `settings/models.yaml` with `supports_video: true`
- **AND** a `youtube_long_processing` step default SHALL exist for the long-video strategy
