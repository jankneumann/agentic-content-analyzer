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

Proofreading SHALL be applied after transcript retrieval and before markdown conversion, for both playlist and RSS transcript ingestion.

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

### Requirement: YouTube Transcript Retry with Exponential Backoff
The system SHALL retry transcript fetch operations that fail with HTTP 429 (Too Many Requests) using exponential backoff.

The retry logic SHALL:
1. Catch 429 errors from `youtube-transcript-api` responses
2. Wait for `base * 2^attempt` seconds (with ±20% jitter) before retrying
3. Retry up to `YOUTUBE_MAX_RETRIES` times (default: 4, giving delays of 2s, 4s, 8s, 16s)
4. After exhausting retries, skip the video and continue with the next one
5. Log each retry attempt with the delay and attempt number

#### Scenario: youtube-transcript-api returns 429
- **WHEN** `youtube-transcript-api` raises an error indicating HTTP 429
- **THEN** the system waits for the backoff delay (2s on first retry)
- **AND** retries the transcript fetch
- **AND** doubles the delay on each subsequent 429 (2s → 4s → 8s → 16s)
- **AND** after `YOUTUBE_MAX_RETRIES` failures, logs a warning and skips the video

#### Scenario: Non-429 errors are not retried
- **WHEN** a transcript fetch fails with an error other than 429 (e.g., 403, 404, transcripts disabled)
- **THEN** the system does not retry
- **AND** proceeds with normal error handling (skip video)

#### Scenario: Backoff jitter prevents thundering herd
- **WHEN** multiple transcript fetches trigger retries simultaneously
- **THEN** each retry delay includes ±20% random jitter
- **AND** the actual delay varies (e.g., 2s ± 0.4s for the first retry)

### Requirement: YouTube Transcript Settings
The system SHALL provide the following settings for controlling YouTube transcript retry behavior:
- `YOUTUBE_MAX_RETRIES` — integer, default `4`. Maximum number of retry attempts on 429 rate-limit errors.
- `YOUTUBE_BACKOFF_BASE` — float, default `2.0`. Base delay in seconds for exponential backoff.
- `YOUTUBE_OAUTH_TOKEN_JSON` — string, optional. JSON content of the OAuth token for headless cloud deployments.

#### Scenario: Retry settings control backoff behavior
- **WHEN** `YOUTUBE_MAX_RETRIES=2` and `YOUTUBE_BACKOFF_BASE=5` are set
- **THEN** the system retries at most 2 times with delays of 5s and 10s

### Requirement: Cloud OAuth Token Hydration
The system SHALL support loading YouTube OAuth credentials from the `YOUTUBE_OAUTH_TOKEN_JSON` environment variable for headless cloud deployments where browser-based OAuth flows are unavailable.

OAuth is only needed for private playlists. Public playlists work with API key (`GOOGLE_API_KEY` / `YOUTUBE_API_KEY`) and RSS feeds use feedparser (no YouTube API needed for discovery).

#### Scenario: Token hydrated from environment variable on cloud startup
- **WHEN** the `YOUTUBE_OAUTH_TOKEN_JSON` environment variable is set
- **AND** the `youtube_token.json` file does not exist on disk
- **THEN** the system writes the env var content to the token file path before loading credentials
- **AND** proceeds with normal OAuth authentication (refresh token → access token)

#### Scenario: Token file takes precedence over environment variable
- **WHEN** both `youtube_token.json` exists on disk and `YOUTUBE_OAUTH_TOKEN_JSON` is set
- **THEN** the system uses the on-disk token file
- **AND** does not overwrite it with the env var content

#### Scenario: Refresh token renewal in cloud
- **WHEN** the access token in the hydrated credentials has expired
- **THEN** the system refreshes the access token using the refresh token via `creds.refresh(Request())`
- **AND** saves the refreshed token to the file (ephemeral in cloud, but valid for the current run)
- **AND** does not require user interaction

#### Scenario: Revoked refresh token in cloud
- **WHEN** the refresh token in `YOUTUBE_OAUTH_TOKEN_JSON` has been revoked in Google Cloud Console
- **THEN** the system logs an error with instructions to re-generate the token locally
- **AND** falls back to API key authentication (if available)
- **AND** private playlists are skipped

### Requirement: Pipeline Ingestion YouTube Split
The `aca pipeline daily` and `aca pipeline weekly` commands SHALL run YouTube playlist ingestion and YouTube RSS ingestion as separate parallel tasks within the ingestion stage.

#### Scenario: Pipeline runs playlists and RSS feeds as independent parallel tasks
- **WHEN** `aca pipeline daily` runs the ingestion stage
- **THEN** `youtube-playlist` and `youtube-rss` run as separate concurrent tasks alongside Gmail, RSS, Podcast, and Substack
- **AND** a rate-limit failure in `youtube-rss` does not block `youtube-playlist`
- **AND** results report counts separately: `youtube-playlist: N items`, `youtube-rss: M items`

#### Scenario: Pipeline YouTube RSS feeds included
- **WHEN** `aca pipeline daily` runs
- **THEN** YouTube RSS feeds from `youtube_rss.yaml` are ingested as part of the pipeline
- **AND** this fixes the current gap where RSS feeds were not included in the pipeline ingestion stage

## MODIFIED Requirements

### Requirement: YouTube Source Visibility and OAuth Graceful Degradation
YouTube source entries (`youtube_playlist`, `youtube_channel`) SHALL support a `visibility` field with values `public` (default) or `private`.

When the YouTube OAuth token is expired or unavailable, the system SHALL:
1. Log a warning about the OAuth token status
2. Skip all sources with `visibility: private`
3. Fall back to the API key (`GOOGLE_API_KEY` / `YOUTUBE_API_KEY`) for `visibility: public` sources
4. Use `youtube-transcript-api` for all transcripts
5. Continue ingestion without crashing

#### Scenario: OAuth available — all sources ingested
- **WHEN** the YouTube OAuth token is valid
- **THEN** the system ingests both `public` and `private` YouTube playlist sources using OAuth credentials

#### Scenario: OAuth expired — public sources continue via API key
- **WHEN** the YouTube OAuth token is expired or revoked
- **AND** a valid `GOOGLE_API_KEY` or `YOUTUBE_API_KEY` is configured
- **THEN** the system ingests `visibility: public` sources using the API key
- **AND** skips `visibility: private` sources with a warning log per source
- **AND** the warning includes the source name and suggests re-authenticating

#### Scenario: OAuth expired, no API key — all YouTube playlist sources skipped
- **WHEN** the YouTube OAuth token is expired and no API key is configured
- **THEN** the system skips all YouTube playlist/channel sources with an error log
- **AND** YouTube RSS feed ingestion continues (uses feedparser, no API key needed for discovery)
- **AND** continues processing non-YouTube sources (RSS, Gmail, Podcast)
