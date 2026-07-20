# YouTube Ingestion (duration-routed processing)

## ADDED Requirements

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
