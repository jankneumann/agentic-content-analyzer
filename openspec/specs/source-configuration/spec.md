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
4. Continue ingestion without crashing

#### Scenario: OAuth available — all sources ingested
- **WHEN** the YouTube OAuth token is valid
- **THEN** the system ingests both `public` and `private` YouTube sources using OAuth credentials

#### Scenario: OAuth expired — public sources continue via API key
- **WHEN** the YouTube OAuth token is expired or revoked
- **AND** a valid `GOOGLE_API_KEY` or `YOUTUBE_API_KEY` is configured
- **THEN** the system ingests `visibility: public` sources using the API key
- **AND** skips `visibility: private` sources with a warning log per source
- **AND** the warning includes the source name and suggests re-authenticating

#### Scenario: OAuth expired, no API key — all YouTube sources skipped
- **WHEN** the YouTube OAuth token is expired and no API key is configured
- **THEN** the system skips all YouTube sources with an error log
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
