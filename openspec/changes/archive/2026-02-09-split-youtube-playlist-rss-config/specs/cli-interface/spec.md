## ADDED Requirements

### Requirement: YouTube Playlist Ingest Subcommand
The system SHALL provide `aca ingest youtube-playlist` as a dedicated subcommand for ingesting YouTube playlist and channel sources from `sources.d/youtube_playlist.yaml`.

#### Scenario: Ingest YouTube playlists only
- **WHEN** `aca ingest youtube-playlist --max <count> --days <days> --force --public-only` is executed
- **THEN** the system ingests videos from playlist and channel sources in `youtube_playlist.yaml`
- **AND** does not process RSS feed sources from `youtube_rss.yaml`
- **AND** displays a summary of ingested items

#### Scenario: YouTube playlist ingest with no playlists configured
- **WHEN** `aca ingest youtube-playlist` is executed
- **AND** no playlist or channel sources exist in `youtube_playlist.yaml`
- **THEN** a message SHALL indicate "No YouTube playlists configured"
- **AND** exit code SHALL be 0

### Requirement: YouTube RSS Ingest Subcommand
The system SHALL provide `aca ingest youtube-rss` as a dedicated subcommand for ingesting YouTube RSS feed sources from `sources.d/youtube_rss.yaml`.

#### Scenario: Ingest YouTube RSS feeds only
- **WHEN** `aca ingest youtube-rss --max <count> --days <days> --force` is executed
- **THEN** the system ingests videos from RSS feed sources in `youtube_rss.yaml`
- **AND** does not process playlist or channel sources from `youtube_playlist.yaml`
- **AND** displays a summary of ingested items

#### Scenario: YouTube RSS ingest with no feeds configured
- **WHEN** `aca ingest youtube-rss` is executed
- **AND** no RSS feed sources exist in `youtube_rss.yaml`
- **THEN** a message SHALL indicate "No YouTube RSS feeds configured"
- **AND** exit code SHALL be 0

## MODIFIED Requirements

### Requirement: Ingest subcommands
The system SHALL provide `aca ingest` subcommands for all supported ingestion sources: gmail, rss, youtube, youtube-playlist, youtube-rss, podcast, and files.

#### Scenario: Ingest Gmail
- **WHEN** `aca ingest gmail --query <query> --max <count> --days <days> --force` is executed
- **THEN** Gmail ingestion SHALL run with the provided options
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest RSS
- **WHEN** `aca ingest rss --max <count> --days <days> --force` is executed
- **THEN** RSS ingestion SHALL run using feeds from `sources.d/rss.yaml`
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest YouTube (combined)
- **WHEN** `aca ingest youtube --max <count> --force` is executed
- **THEN** YouTube ingestion SHALL run playlists from `sources.d/youtube_playlist.yaml` first, then RSS feeds from `sources.d/youtube_rss.yaml`
- **AND** a summary of ingested items SHALL be displayed with playlists, channels, and feeds counts

#### Scenario: Ingest YouTube Playlist
- **WHEN** `aca ingest youtube-playlist --max <count> --force` is executed
- **THEN** YouTube playlist ingestion SHALL run using sources from `sources.d/youtube_playlist.yaml`
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest YouTube RSS
- **WHEN** `aca ingest youtube-rss --max <count> --force` is executed
- **THEN** YouTube RSS ingestion SHALL run using feeds from `sources.d/youtube_rss.yaml`
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest Podcast
- **WHEN** `aca ingest podcast --max <count> --transcribe --force` is executed
- **THEN** podcast ingestion SHALL run using feeds from `sources.d/podcasts.yaml`
- **AND** the `--transcribe` flag SHALL control whether audio transcription is attempted
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest files
- **WHEN** `aca ingest files <path...>` is executed
- **THEN** the specified files SHALL be ingested via the file ingestion service
- **AND** supported formats (PDF, markdown, HTML) SHALL be parsed

#### Scenario: Ingestion with missing credentials
- **GIVEN** required credentials (e.g., Gmail OAuth, YouTube API key) are not configured
- **WHEN** `aca ingest gmail` is executed
- **THEN** a clear error message SHALL indicate which credentials are missing
- **AND** exit code SHALL be 1

#### Scenario: Ingestion with no new content
- **WHEN** `aca ingest rss` is executed
- **AND** no new content is found
- **THEN** a message SHALL indicate "No new content found"
- **AND** exit code SHALL be 0
