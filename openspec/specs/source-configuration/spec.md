# source-configuration Specification

## Purpose
TBD - created by archiving change add-ingest-source-configuration. Update Purpose after archive.
## Requirements
### Requirement: Unified Source Configuration File
The system SHALL load ingestion source definitions from YAML configuration files. The system SHALL support two layouts:
1. **Directory layout** (`sources.d/`): Multiple YAML files split by source type, loaded alphabetically and merged
2. **Single file layout** (`sources.yaml`): All sources in one file

Each YAML file SHALL support a `defaults` section and a `sources` list. Defaults (including `type`) cascade: `_defaults.yaml` globals → per-file `defaults` → per-entry fields (most specific wins). This allows type-specific files (e.g., `rss.yaml` with `defaults.type: rss`) and topic-based mixed-type files (e.g., `ai-research.yaml` with `type` per entry).

#### Scenario: Load sources from `sources.d/` directory
- **WHEN** a `sources.d/` directory exists at the project root
- **THEN** the system loads all `*.yaml` files from the directory in alphabetical order
- **AND** merges all `sources` lists into a single validated `SourcesConfig`
- **AND** applies defaults from `_defaults.yaml` (if present) to all sources
- **AND** sources with `enabled: false` are excluded from ingestion

#### Scenario: Load sources from single `sources.yaml`
- **WHEN** `sources.d/` does not exist but `sources.yaml` exists at the configured path
- **THEN** the system loads and validates all source entries from the single file using Pydantic models
- **AND** sources with `enabled: false` are excluded from ingestion

#### Scenario: Fallback to legacy config files
- **WHEN** neither `sources.d/` nor `sources.yaml` exist
- **THEN** the system falls back to reading `rss_feeds.txt` and `youtube_playlists.txt`
- **AND** a warning is logged recommending migration to `sources.d/`

#### Scenario: Per-file type default
- **WHEN** a YAML file in `sources.d/` defines `defaults: { type: rss }`
- **THEN** all source entries in that file inherit `type: rss` unless the entry overrides `type` explicitly
- **AND** entries without a `url` field (required for `type: rss`) still fail validation

#### Scenario: Topic-based mixed-type file
- **WHEN** a YAML file defines sources with different `type` values per entry and no `type` in `defaults`
- **THEN** each entry is validated independently using its own `type` discriminator
- **AND** entries missing `type` (with no file-level default) raise a validation error

#### Scenario: Invalid YAML config
- **WHEN** any YAML config file contains invalid entries (missing required fields, unknown type)
- **THEN** the system raises a validation error with specific field-level details including the filename
- **AND** valid sources are not partially loaded (fail-fast behavior)

### Requirement: Source Type Support
The system SHALL support the following source types in the configuration file:
- `rss` — RSS/Atom article feeds
- `youtube_playlist` — YouTube playlist IDs
- `youtube_channel` — YouTube channel IDs (resolved to uploads playlist)
- `youtube_rss` — YouTube channel RSS feeds
- `podcast` — Podcast RSS feeds with audio enclosures
- `gmail` — Gmail inbox queries
- `websearch` — Web search sources (Perplexity, Grok) with per-entry provider and prompt

#### Scenario: RSS source entry
- **WHEN** a source with `type: rss` and `url` field is defined
- **THEN** the system includes it in RSS ingestion with optional `name`, `tags`, and `max_entries` override

#### Scenario: YouTube playlist source entry
- **WHEN** a source with `type: youtube_playlist` and `id` field is defined
- **THEN** the system ingests videos from the playlist using the existing `ingest_playlist()` method
- **AND** respects the `visibility` field for OAuth graceful degradation

#### Scenario: YouTube channel source entry
- **WHEN** a source with `type: youtube_channel` and `channel_id` field is defined
- **THEN** the system resolves the channel ID to an uploads playlist ID via the YouTube Data API
- **AND** ingests videos from the resolved playlist

#### Scenario: YouTube RSS source entry
- **WHEN** a source with `type: youtube_rss` and `url` field is defined
- **THEN** the system parses the YouTube RSS feed to extract video IDs and metadata
- **AND** fetches transcripts for discovered videos using the existing transcript pipeline

#### Scenario: Podcast source entry
- **WHEN** a source with `type: podcast` and `url` field is defined
- **THEN** the system fetches the podcast RSS feed and applies the transcript-first strategy
- **AND** stores the transcript as a Content record with `source_type=PODCAST`

### Requirement: Per-Source Metadata
Each source entry SHALL support optional metadata fields: `name` (human-readable label), `tags` (list of categorization strings), and `enabled` (boolean toggle).

Source metadata SHALL be stored in the Content record's `metadata_json` field during ingestion.

#### Scenario: Source metadata propagation
- **WHEN** a source with `name: "Latent Space"` and `tags: ["ai", "engineering"]` is ingested
- **THEN** the resulting Content records include `{"source_name": "Latent Space", "source_tags": ["ai", "engineering"]}` in `metadata_json`

#### Scenario: Disabled source skipped
- **WHEN** a source has `enabled: false`
- **THEN** the system skips it during ingestion without error
- **AND** logs a debug message indicating the source was skipped

### Requirement: YouTube Channel Resolution
The system SHALL resolve YouTube channel IDs to their uploads playlist IDs using the YouTube Data API `channels().list(part="contentDetails")` endpoint.

Resolved mappings SHALL be cached to avoid repeated API calls for the same channel.

#### Scenario: Channel ID resolution
- **WHEN** a `youtube_channel` source with `channel_id: UCbfYPyITQ-7l4upoX8nvctg` is processed
- **THEN** the system calls the YouTube Data API to retrieve the uploads playlist ID
- **AND** passes the resolved playlist ID to the existing `ingest_playlist()` method

#### Scenario: Invalid channel ID
- **WHEN** a `youtube_channel` source has an invalid or deleted channel ID
- **THEN** the system logs an error and continues processing other sources
- **AND** does not crash or halt ingestion

### Requirement: Podcast RSS Ingestion with Transcript-First Strategy
The system SHALL ingest podcast episodes from RSS feeds using a three-tier transcript acquisition strategy:
1. **Tier 1 — Feed-embedded transcript**: Check `<content:encoded>`, `<description>`, and `<itunes:summary>` for text content ≥ 500 characters
2. **Tier 2 — Linked transcript page**: Scan show notes for transcript URLs (patterns: `/transcript`, `/show-notes`), fetch and extract via Trafilatura
3. **Tier 3 — Audio STT fallback**: If `transcribe: true` and an audio `<enclosure>` exists, download audio and transcribe via configured STT provider

The system SHALL store the `raw_format` field indicating which tier produced the transcript: `feed_transcript`, `linked_transcript`, or `audio_transcript`.

#### Scenario: Episode with feed-embedded transcript (Tier 1)
- **WHEN** a podcast feed entry contains `<content:encoded>` with ≥ 500 characters of text
- **THEN** the system uses the embedded text as the transcript without downloading audio
- **AND** sets `raw_format` to `feed_transcript`
- **AND** the `source_id` is set to `podcast:{episode_guid}`

#### Scenario: Episode with linked transcript page (Tier 2)
- **WHEN** a podcast feed entry's show notes contain a URL matching transcript patterns
- **AND** the linked page contains extractable text content
- **THEN** the system fetches the page, extracts text via Trafilatura, and uses it as the transcript
- **AND** sets `raw_format` to `linked_transcript`

#### Scenario: Episode with audio-only, transcription enabled (Tier 3)
- **WHEN** no text transcript is found in Tier 1 or Tier 2
- **AND** the source has `transcribe: true` and the episode has an audio `<enclosure>`
- **THEN** the system downloads the audio, transcribes via STT, and stores the result
- **AND** sets `raw_format` to `audio_transcript`
- **AND** cleans up the temporary audio file after transcription

#### Scenario: Episode with no transcript and transcription disabled
- **WHEN** no text transcript is found in Tier 1 or Tier 2
- **AND** the source has `transcribe: false` or no audio enclosure exists
- **THEN** the system stores a metadata-only Content record (title, date, description)
- **AND** logs a warning indicating no transcript was available

#### Scenario: Transcription failure (Tier 3)
- **WHEN** the STT provider fails to transcribe an audio file
- **THEN** the system logs the error, cleans up the temp file, and continues
- **AND** falls back to storing metadata-only Content

### Requirement: YouTube Source Visibility and OAuth Graceful Degradation
YouTube source entries (`youtube_playlist`, `youtube_channel`) SHALL support a `visibility` field with values `public` (default) or `private`.

When the YouTube OAuth token is expired or unavailable, the system SHALL:
1. Log a warning about the OAuth token status
2. Skip all sources with `visibility: private`
3. Fall back to the API key (`GOOGLE_API_KEY` / `YOUTUBE_API_KEY`) for `visibility: public` sources
4. Use Gemini native extraction for transcripts when `gemini_summary: true` (default) and `GOOGLE_API_KEY` is set; fall back to `youtube-transcript-api` only when Gemini is disabled or unavailable
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

### Requirement: Migration Script
The system SHALL provide a CLI migration script that converts existing configuration files into the `sources.d/` directory layout or a single `sources.yaml`.

The script SHALL support importing from `rss_feeds.txt`, `youtube_playlists.txt`, and optionally from the `AI-ML-Data-News.md` reference file.

#### Scenario: Migrate to split directory layout (default)
- **WHEN** the migration script is run with `--output-dir sources.d`
- **THEN** it creates `sources.d/` with separate files per type: `_defaults.yaml`, `rss.yaml`, `youtube.yaml`, `podcasts.yaml`, `gmail.yaml`
- **AND** each file contains only sources of its type

#### Scenario: Migrate to single file
- **WHEN** the migration script is run with `--output sources.yaml`
- **THEN** it reads `rss_feeds.txt` and `youtube_playlists.txt`
- **AND** outputs a valid `sources.yaml` with all entries in a single file

#### Scenario: Migrate with markdown reference
- **WHEN** the migration script is run with `--from-markdown AI-ML-Data-News.md`
- **THEN** it parses the markdown sections for news feeds, podcasts, and YouTube channels
- **AND** extracts name, URL, and RSS feed URL from each entry
- **AND** deduplicates entries that appear in both the markdown and existing config files

#### Scenario: Deduplication across inputs
- **WHEN** the same RSS URL appears in both `rss_feeds.txt` and `AI-ML-Data-News.md`
- **THEN** the migration script keeps one entry and preserves the richest metadata (name, description)

### Requirement: Source Configuration Settings
The system SHALL provide the following settings for source configuration:
- `SOURCES_CONFIG_DIR` — path to `sources.d/` directory (default: `sources.d` in project root)
- `SOURCES_CONFIG_FILE` — path to `sources.yaml` fallback (default: `sources.yaml` in project root)
- `PODCAST_STT_PROVIDER` — STT provider for podcast transcription (`openai` or `local_whisper`, default: `openai`)
- `PODCAST_MAX_DURATION_MINUTES` — maximum episode duration to transcribe (default: `120`)
- `PODCAST_TEMP_DIR` — temporary directory for audio downloads (default: `/tmp/podcast_downloads`)

#### Scenario: Custom config directory path
- **WHEN** `SOURCES_CONFIG_DIR=config/sources.d` is set
- **THEN** the system loads sources from `config/sources.d/*.yaml` instead of the default path

#### Scenario: Custom config file path (single file fallback)
- **WHEN** `SOURCES_CONFIG_DIR` does not exist and `SOURCES_CONFIG_FILE=config/my-sources.yaml` is set
- **THEN** the system loads sources from `config/my-sources.yaml` instead of the default path

#### Scenario: Podcast settings override
- **WHEN** `PODCAST_STT_PROVIDER=local_whisper` is set
- **THEN** podcast transcription uses local Whisper instead of OpenAI API

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

### Requirement: Gemini Native YouTube Video Content Extraction
The system SHALL support using Gemini's native YouTube URL processing to extract detailed content from videos, bypassing `youtube-transcript-api` entirely.

Ingestion and summarization remain **separate steps**. The Gemini ingestion step produces a detailed content extraction — a comprehensive account of the video's content (topics discussed, arguments made, examples given, technical details, speaker attributions). This is stored as the Content record's `content` field, analogous to a transcript. The existing summarization pipeline (`aca summarize pending`) then processes it with its own prompts and detail levels, just like any other content source.

The Gemini content extraction SHALL:
1. Use `Part.from_uri(file_uri=youtube_url, mime_type="video/mp4")` to pass the YouTube URL directly to Gemini
2. Include a content extraction prompt requesting comprehensive coverage: all topics discussed, technical details, speaker statements, examples, and arguments — without editorial filtering
3. Store the result as `ContentSource.YOUTUBE` with `metadata_json` containing `"processing_method": "gemini_native"`
4. Allow the content to proceed through the normal summarization pipeline (no special handling in the summarizer)

**Two-tier model configuration:**
- Playlist ingestion: `YOUTUBE_PROCESSING` ModelStep (default: `gemini-2.5-flash`) — higher quality for curated content
- RSS feed ingestion: `YOUTUBE_RSS_PROCESSING` ModelStep (default: `gemini-2.5-flash-lite`) — cheapest for bulk processing

**Resolution control via Gemini API `media_resolution` parameter:**
- RSS feeds: `LOW` resolution (66 tokens/frame) — ~3x cheaper than default
- Playlists: `default` resolution (258 tokens/frame) — better quality for curated content
- Configurable per-source via `gemini_resolution` field in YAML config
- Note: Resolution is controlled via the Gemini API `GenerateContentConfig.media_resolution` parameter, not via the YouTube URL

**Source configuration fields:**
- `gemini_summary: bool` (default: `true`) — enable/disable Gemini native content extraction per-source
- `gemini_resolution: str` (default: varies by source type) — `low`, `medium`, `high`, or `default`

#### Scenario: Gemini content extraction for playlist video
- **WHEN** a playlist source has `gemini_summary: true` (default)
- **AND** `GOOGLE_API_KEY` is set
- **THEN** the system sends the YouTube URL to Gemini via `Part.from_uri`
- **AND** the Gemini response is stored as the Content record's `content` field with `processing_method: gemini_native` in metadata
- **AND** the `YOUTUBE_PROCESSING` ModelStep model is used (default: `gemini-2.5-flash`)
- **AND** the content proceeds through the normal summarization pipeline

#### Scenario: Gemini content extraction for RSS feed video with low resolution
- **WHEN** an RSS feed source has `gemini_summary: true` and `gemini_resolution: low` (RSS default)
- **AND** `GOOGLE_API_KEY` is set
- **THEN** the system sends the YouTube URL to Gemini with `media_resolution=LOW`
- **AND** the `YOUTUBE_RSS_PROCESSING` ModelStep model is used (default: `gemini-2.5-flash-lite`)
- **AND** frame processing uses 66 tokens/frame instead of 258 (3x cost reduction)

#### Scenario: Gemini-ingested content goes through normal summarization
- **WHEN** `aca summarize pending` encounters content with `processing_method: gemini_native` in metadata
- **THEN** the summarizer processes it using the standard summarization prompt and `SUMMARIZATION` ModelStep
- **AND** the summary captures relevance, key insights, and theme tags for the digest
- **AND** no special-casing is needed in the summarizer

#### Scenario: Fallback to transcript when GOOGLE_API_KEY not set
- **WHEN** `gemini_summary: true` but `GOOGLE_API_KEY` is not set
- **THEN** the system logs a warning and falls back to `youtube-transcript-api` for transcript fetching
- **AND** the content goes through the normal summarization pipeline

#### Scenario: Fallback to transcript for private/unlisted video
- **WHEN** Gemini returns an error for a specific video (e.g., video is private or unlisted)
- **THEN** the system falls back to `youtube-transcript-api` for that video only
- **AND** other videos in the same source continue with Gemini content extraction
- **AND** the fallback is logged with the video ID and error reason

#### Scenario: Gemini content extraction disabled per-source
- **WHEN** a source sets `gemini_summary: false`
- **THEN** the system uses `youtube-transcript-api` for all videos from that source
- **AND** the content goes through the normal summarization pipeline

### Requirement: LLM-Based YouTube Caption Proofreading
The system SHALL provide a post-processing proofread step that uses a fast LLM to contextually correct phonetic misspellings of proper nouns in auto-generated YouTube captions.

The proofread function SHALL:
1. Accept a list of `TranscriptSegment` objects and a list of hint terms (proper nouns likely to appear)
2. Batch segments (~50 per LLM call) and send them with a proofreading prompt that includes hint terms and domain context
3. Use the LLM to identify and correct only proper noun misspellings, preserving all other text exactly
4. Return corrected `TranscriptSegment` objects with an `is_proofread` flag set to `true`

The model SHALL be configurable via a new `CAPTION_PROOFREADING` pipeline step:
- Default model: `gemini-2.5-flash-lite` (fastest, cheapest option)
- Configurable via `MODEL_CAPTION_PROOFREADING` env var (e.g., `claude-haiku-4-5`)

Hint terms SHALL be configurable via:
- A `hint_terms` list in the YouTube playlist source entry (per-playlist additions)
- A top-level `hint_terms` list under `defaults` in `youtube_playlist.yaml` (shared baseline)
- Built-in defaults for common AI terminology (e.g., "Claude", "Anthropic", "OpenAI", "LLaMA", "ChatGPT", "Gemini", "Mistral")

Proofreading SHALL be applied after transcript retrieval and before markdown conversion, only for auto-generated captions.

#### Scenario: Auto-generated captions with contextual misspelling correction
- **WHEN** a video transcript contains "cloud" in a sentence like "cloud is an AI model made by anthropic"
- **AND** the hint terms include "Claude" and "Anthropic"
- **THEN** the LLM corrects "cloud" to "Claude" and "anthropic" to "Anthropic" based on context
- **AND** the corrected transcript is used for markdown conversion
- **AND** the Content record's `metadata_json` includes `"is_proofread": true`

#### Scenario: Legitimate words preserved in correct context
- **WHEN** a video transcript contains "cloud" in a sentence like "deploying to the cloud using AWS"
- **THEN** the LLM preserves "cloud" as-is because it is correct in this context
- **AND** no false-positive correction occurs

#### Scenario: Per-playlist hint terms
- **WHEN** a playlist source in `youtube_playlist.yaml` defines a `hint_terms` list
- **THEN** those terms are merged with the shared defaults
- **AND** the combined list is passed to the LLM prompt for that playlist's videos

#### Scenario: Manual captions skip proofreading
- **WHEN** a video has manually created captions (not auto-generated)
- **THEN** the proofread step is skipped
- **AND** the transcript is used as-is

#### Scenario: Proofreading disabled
- **WHEN** a playlist source sets `proofread: false`
- **THEN** no LLM proofreading is applied to transcripts from that playlist

#### Scenario: Proofreading model configurable
- **WHEN** `MODEL_CAPTION_PROOFREADING=claude-haiku-4-5` is set in the environment
- **THEN** the proofreading step uses Claude Haiku instead of the default Gemini Flash Lite
- **AND** the model is resolved via the existing `ModelConfig.get_model_for_step()` mechanism

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

### Requirement: Web Search Source Type

The system SHALL recognize `websearch` as a valid source type in `sources.d/` directory configuration.

#### Scenario: Loading websearch source file

- **WHEN** the source loader reads `sources.d/websearch.yaml`
- **THEN** each entry is parsed as a `WebSearchSource` with required fields: `name`, `provider`, `prompt`
- **AND** optional fields: `enabled` (default: true), `tags` (default: []), provider-specific overrides
- **AND** the `provider` field accepts values: `perplexity`, `grok`
- **AND** entries with unrecognized provider values are logged as warnings and skipped

#### Scenario: Websearch source defaults

- **WHEN** `sources.d/websearch.yaml` has a `defaults` section with `type: websearch` and `enabled: true`
- **THEN** all entries inherit the defaults unless explicitly overridden
- **AND** the cascading defaults pattern matches other source types (global defaults → file defaults → per-entry fields)

#### Scenario: Invalid websearch source entry

- **WHEN** a websearch source entry is missing the required `prompt` field or has an invalid `provider` value
- **THEN** the source loader logs a warning identifying the entry
- **AND** the entry is excluded from the loaded sources
- **AND** valid entries in the same file are still loaded

#### Scenario: Provider-specific source fields

- **WHEN** a websearch source entry includes provider-specific fields:
  - Perplexity: `max_results`, `recency_filter`, `context_size`, `domain_filter`
  - Grok: `max_threads`
- **THEN** these fields are passed to the respective provider's orchestrator function
- **AND** fields not applicable to the specified provider are ignored with a debug log

### Requirement: Source Directory Layout — Websearch

The system SHALL include `websearch.yaml` as part of the standard `sources.d/` directory structure alongside existing source files.

#### Scenario: Complete source directory

- **WHEN** the source directory is listed
- **THEN** `websearch.yaml` appears alongside `_defaults.yaml`, `rss.yaml`, `youtube_playlist.yaml`, `youtube_rss.yaml`, `podcasts.yaml`, `gmail.yaml`, `substack.yaml`
- **AND** the file follows the same YAML structure pattern: `defaults` section + `sources` array
