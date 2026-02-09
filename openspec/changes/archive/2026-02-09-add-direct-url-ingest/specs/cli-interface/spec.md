## MODIFIED Requirements
### Requirement: Ingest subcommands
The system SHALL provide `aca ingest` subcommands for all supported ingestion sources: gmail, rss, youtube, podcast, files, and direct URLs.

#### Scenario: Ingest Gmail
- **WHEN** `aca ingest gmail --query <query> --max <count> --days <days> --force` is executed
- **THEN** Gmail ingestion SHALL run with the provided options
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest RSS
- **WHEN** `aca ingest rss --max <count> --days <days> --force` is executed
- **THEN** RSS ingestion SHALL run using feeds from `sources.d/rss.yaml`
- **AND** a summary of ingested items SHALL be displayed

#### Scenario: Ingest YouTube
- **WHEN** `aca ingest youtube --max <count> --force` is executed
- **THEN** YouTube ingestion SHALL run using playlists from `sources.d/youtube.yaml`
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

#### Scenario: Ingest URL
- **WHEN** `aca ingest url <url>` is executed
- **THEN** the URL SHALL be submitted to the save-url workflow
- **AND** the returned content ID and status SHALL be displayed

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
