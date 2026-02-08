## ADDED Requirements

### Requirement: YouTube Source File Split
The system SHALL support separate YAML configuration files for YouTube playlist sources and YouTube RSS feed sources:
- `youtube_playlist.yaml` — contains `youtube_playlist` and `youtube_channel` source entries
- `youtube_rss.yaml` — contains `youtube_rss` source entries

Both files SHALL be loaded by the existing `load_sources_directory` function and merged into the unified `SourcesConfig`. The split is transparent to the loader — source type filtering occurs via `get_youtube_playlist_sources()`, `get_youtube_channel_sources()`, and `get_youtube_rss_sources()`.

#### Scenario: Playlist sources loaded from youtube_playlist.yaml
- **WHEN** `sources.d/youtube_playlist.yaml` contains entries with `type: youtube_playlist`
- **THEN** the system loads and validates them as `YouTubePlaylistSource` objects
- **AND** they are returned by `config.get_youtube_playlist_sources()`
- **AND** `youtube_rss` entries in `youtube_rss.yaml` are not included

#### Scenario: RSS sources loaded from youtube_rss.yaml
- **WHEN** `sources.d/youtube_rss.yaml` contains entries with `type: youtube_rss`
- **THEN** the system loads and validates them as `YouTubeRSSSource` objects
- **AND** they are returned by `config.get_youtube_rss_sources()`
- **AND** `youtube_playlist` entries in `youtube_playlist.yaml` are not included

#### Scenario: Backward compatible with single youtube.yaml
- **WHEN** `sources.d/youtube.yaml` exists with mixed `youtube_playlist` and `youtube_rss` entries
- **AND** `youtube_playlist.yaml` and `youtube_rss.yaml` do not exist
- **THEN** the system loads all entries from `youtube.yaml` as before
- **AND** type filtering returns the correct sources for each service

### Requirement: YouTube Data API Captions for Playlist Ingestion
The system SHALL support fetching video transcripts via the YouTube Data API `captions` endpoint as an alternative to the `youtube-transcript-api` library for playlist-sourced videos.

When OAuth credentials are available, the playlist ingestion service SHALL:
1. Call `captions.list(videoId=...)` to discover available caption tracks
2. Select the best track matching the preferred language (manual captions preferred over auto-generated)
3. Call `captions.download(id=..., tfmt='srt')` to download the caption track in SRT format
4. Parse the SRT content into `TranscriptSegment` objects

When the Data API captions call fails (e.g., video not owned by OAuth user, no captions available), the system SHALL fall back to the `youtube-transcript-api` library for that specific video.

When OAuth is not available (API key only), the system SHALL use `youtube-transcript-api` directly, matching current behavior.

#### Scenario: Transcript fetched via Data API captions with OAuth
- **WHEN** a playlist video is being ingested
- **AND** OAuth credentials are available
- **AND** `YOUTUBE_PREFER_DATA_API_CAPTIONS` is `true` (default)
- **THEN** the system calls `captions.list` to discover tracks for the video
- **AND** selects the best matching track (manual > auto-generated, preferred language)
- **AND** downloads the track via `captions.download` in SRT format
- **AND** parses SRT into `TranscriptSegment` objects
- **AND** the resulting Content record has `parser_used` set to `youtube_data_api_captions`

#### Scenario: Data API captions fallback to youtube-transcript-api
- **WHEN** a playlist video is being ingested via Data API captions
- **AND** the `captions.download` call fails (e.g., `HttpError 403` for non-owned video)
- **THEN** the system falls back to `youtube-transcript-api` for that video
- **AND** logs the fallback at `DEBUG` level
- **AND** the resulting Content record has `parser_used` set to `youtube_transcript_api`

#### Scenario: Data API captions disabled by setting
- **WHEN** `YOUTUBE_PREFER_DATA_API_CAPTIONS` is set to `false`
- **THEN** playlist ingestion uses `youtube-transcript-api` for all transcripts
- **AND** no `captions.list` or `captions.download` API calls are made

#### Scenario: API key only — no Data API captions
- **WHEN** OAuth credentials are not available
- **AND** the system authenticates with API key only
- **THEN** the system uses `youtube-transcript-api` for all transcripts
- **AND** logs that Data API captions require OAuth

#### Scenario: RSS ingestion unchanged
- **WHEN** an RSS feed video is being ingested via `YouTubeRSSIngestionService`
- **THEN** the system uses `youtube-transcript-api` for transcript retrieval
- **AND** does not attempt Data API captions calls

### Requirement: YouTube Caption Proofreading
The system SHALL provide a post-processing proofread step for YouTube captions that corrects phonetic misspellings of proper nouns commonly introduced by auto-generated captions.

The proofread function SHALL:
1. Accept a list of `TranscriptSegment` objects and a corrections dictionary
2. Apply case-insensitive whole-word replacements from the corrections dictionary
3. Return corrected `TranscriptSegment` objects with an `is_proofread` flag set to `true`

The corrections dictionary SHALL be configurable via:
- A `corrections` map in the YouTube playlist source entry (per-playlist overrides)
- A top-level `corrections` map in `youtube_playlist.yaml` (shared defaults)
- Built-in defaults for common AI terminology misspellings (e.g., "clawd"/"cloud" → "Claude", "open eye" → "OpenAI", "lama" → "LLaMA")

Proofreading SHALL be applied after transcript retrieval and before markdown conversion, for both Data API captions and youtube-transcript-api transcripts.

#### Scenario: Auto-generated captions with phonetic misspellings corrected
- **WHEN** a video transcript contains "clawd" or "cloud" in an AI context
- **AND** the corrections dictionary maps these to "Claude"
- **THEN** the proofread step replaces the misspellings with "Claude"
- **AND** the corrected transcript is used for markdown conversion
- **AND** the Content record's `metadata_json` includes `"is_proofread": true`

#### Scenario: Per-playlist correction overrides
- **WHEN** a playlist source in `youtube_playlist.yaml` defines a `corrections` map
- **THEN** those corrections are merged with (and override) the shared defaults
- **AND** only apply to videos from that specific playlist

#### Scenario: Manual captions skip proofreading
- **WHEN** a video has manually created captions (not auto-generated)
- **THEN** the proofread step is skipped
- **AND** the transcript is used as-is

#### Scenario: Proofreading disabled
- **WHEN** a playlist source sets `proofread: false`
- **THEN** no corrections are applied to transcripts from that playlist

### Requirement: YouTube Data API Captions Quota Logging
The system SHALL log YouTube Data API quota usage for captions operations to help operators monitor quota consumption.

#### Scenario: Quota usage logged per ingestion run
- **WHEN** playlist ingestion completes using Data API captions
- **THEN** the system logs the total quota units consumed (captions.list: 50/video, captions.download: 200/video)
- **AND** includes the count of videos that used Data API vs youtube-transcript-api fallback

### Requirement: YouTube Data API Captions Settings
The system SHALL provide the following setting for controlling Data API captions behavior:
- `YOUTUBE_PREFER_DATA_API_CAPTIONS` — boolean, default `true`. When `true` and OAuth is available, playlist ingestion prefers the Data API `captions` endpoint over `youtube-transcript-api`.

#### Scenario: Setting controls transcript strategy
- **WHEN** `YOUTUBE_PREFER_DATA_API_CAPTIONS=false` is set in the environment
- **THEN** all YouTube ingestion uses `youtube-transcript-api` regardless of OAuth availability
- **AND** the Data API is only used for playlist video discovery (not transcripts)

## MODIFIED Requirements

### Requirement: YouTube Source Visibility and OAuth Graceful Degradation
YouTube source entries (`youtube_playlist`, `youtube_channel`) SHALL support a `visibility` field with values `public` (default) or `private`.

When the YouTube OAuth token is expired or unavailable, the system SHALL:
1. Log a warning about the OAuth token status
2. Skip all sources with `visibility: private`
3. Fall back to the API key (`GOOGLE_API_KEY` / `YOUTUBE_API_KEY`) for `visibility: public` sources
4. Use `youtube-transcript-api` for transcripts (Data API captions require OAuth)
5. Continue ingestion without crashing

#### Scenario: OAuth available — all sources ingested with Data API captions
- **WHEN** the YouTube OAuth token is valid
- **THEN** the system ingests both `public` and `private` YouTube playlist sources using OAuth credentials
- **AND** uses Data API `captions` endpoint for transcript retrieval (when `YOUTUBE_PREFER_DATA_API_CAPTIONS` is `true`)
- **AND** falls back to `youtube-transcript-api` for videos where Data API captions fail

#### Scenario: OAuth expired — public sources continue via API key
- **WHEN** the YouTube OAuth token is expired or revoked
- **AND** a valid `GOOGLE_API_KEY` or `YOUTUBE_API_KEY` is configured
- **THEN** the system ingests `visibility: public` sources using the API key
- **AND** uses `youtube-transcript-api` for transcripts (Data API captions unavailable without OAuth)
- **AND** skips `visibility: private` sources with a warning log per source
- **AND** the warning includes the source name and suggests re-authenticating

#### Scenario: OAuth expired, no API key — all YouTube sources skipped
- **WHEN** the YouTube OAuth token is expired and no API key is configured
- **THEN** the system skips all YouTube sources with an error log
- **AND** continues processing non-YouTube sources (RSS, Gmail, Podcast)
