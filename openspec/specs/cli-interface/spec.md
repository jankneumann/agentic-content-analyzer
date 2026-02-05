# cli-interface Specification

## Purpose
TBD - created by archiving change add-aca-cli. Update Purpose after archive.
## Requirements
### Requirement: aca CLI entrypoint
The system SHALL provide a top-level CLI command named `aca`, registered as a console_scripts entrypoint.

#### Scenario: Display help
- **WHEN** `aca --help` is executed
- **THEN** a list of available subcommand groups SHALL be displayed
- **AND** each group SHALL show a brief description

#### Scenario: Display version
- **WHEN** `aca --version` is executed
- **THEN** the installed package version SHALL be printed

#### Scenario: Unknown subcommand
- **WHEN** `aca nonexistent` is executed
- **THEN** an error message SHALL indicate the command is not recognized
- **AND** exit code SHALL be 2

### Requirement: Output format
All CLI commands SHALL use Rich console output by default for human-readable display.

#### Scenario: Default Rich output
- **WHEN** any `aca` command is executed without `--json`
- **THEN** output SHALL be formatted using Rich tables, panels, or styled text

#### Scenario: JSON output
- **WHEN** any `aca` command is executed with `--json`
- **THEN** output SHALL be valid JSON printed to stdout
- **AND** progress messages SHALL be suppressed or sent to stderr

### Requirement: Ingest subcommands
The system SHALL provide `aca ingest` subcommands for all supported ingestion sources: gmail, rss, youtube, podcast, and files.

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

### Requirement: Summarize subcommands
The system SHALL provide `aca summarize` subcommands for content summarization.

#### Scenario: Summarize pending content
- **WHEN** `aca summarize pending --limit <N>` is executed
- **THEN** up to N pending content items SHALL be summarized
- **AND** a count of successfully summarized items SHALL be displayed

#### Scenario: Summarize by id
- **WHEN** `aca summarize id <content-id>` is executed
- **THEN** the specified content item SHALL be summarized

#### Scenario: List summaries
- **WHEN** `aca summarize list --limit <N>` is executed
- **THEN** recent summaries SHALL be listed with id, title, source, and date

#### Scenario: Summarize nonexistent content
- **WHEN** `aca summarize id 99999` is executed
- **AND** no content with that id exists
- **THEN** an error message SHALL indicate the content was not found
- **AND** exit code SHALL be 1

### Requirement: Create digest subcommands
The system SHALL provide `aca create-digest` subcommands for daily and weekly digests.

#### Scenario: Create daily digest
- **WHEN** `aca create-digest daily --date <YYYY-MM-DD>` is executed
- **THEN** a daily digest SHALL be generated for that date
- **AND** the digest id and title SHALL be displayed on success

#### Scenario: Create weekly digest
- **WHEN** `aca create-digest weekly --week <YYYY-MM-DD>` is executed
- **THEN** a weekly digest SHALL be generated for the week containing that date

#### Scenario: Create digest with no summarized content
- **GIVEN** no summarized content exists for the requested date range
- **WHEN** `aca create-digest daily --date 2020-01-01` is executed
- **THEN** an error message SHALL indicate no content is available for that period
- **AND** exit code SHALL be 1

### Requirement: Pipeline subcommands
The system SHALL provide `aca pipeline` subcommands to run ingest → summarize → digest workflows.

#### Scenario: Run daily pipeline
- **WHEN** `aca pipeline daily --date <YYYY-MM-DD>` is executed
- **THEN** the system SHALL sequentially: ingest all sources, summarize pending content, and create a daily digest
- **AND** progress for each stage SHALL be displayed

#### Scenario: Run weekly pipeline
- **WHEN** `aca pipeline weekly --week <YYYY-MM-DD>` is executed
- **THEN** the system SHALL sequentially: ingest all sources, summarize pending content, and create a weekly digest

#### Scenario: Pipeline stage failure
- **GIVEN** the summarization stage fails (e.g., LLM API error)
- **WHEN** `aca pipeline daily` is executed
- **THEN** the error SHALL be reported with the failing stage name
- **AND** exit code SHALL be 1
- **AND** successfully completed stages SHALL NOT be rolled back

### Requirement: Review subcommands
The system SHALL provide `aca review` subcommands for digest review workflows, including interactive revision.

#### Scenario: List pending reviews
- **WHEN** `aca review list` is executed
- **THEN** digests awaiting review SHALL be listed with id, title, type, and date

#### Scenario: View digest for review
- **WHEN** `aca review view <digest-id>` is executed
- **THEN** the full digest content SHALL be displayed in the terminal

#### Scenario: Revise digest interactively
- **WHEN** `aca review revise <digest-id>` is executed
- **THEN** the digest content SHALL be displayed
- **AND** a REPL prompt SHALL accept revision instructions
- **AND** typing "done" or pressing Ctrl-D SHALL finalize the revision
- **AND** each instruction SHALL produce a revised version displayed in the terminal

#### Scenario: Revise nonexistent digest
- **WHEN** `aca review revise 99999` is executed
- **AND** no digest with that id exists
- **THEN** an error message SHALL indicate the digest was not found
- **AND** exit code SHALL be 1

### Requirement: Analyze subcommands
The system SHALL provide `aca analyze` subcommands for theme analysis.

#### Scenario: Analyze themes by date range
- **WHEN** `aca analyze themes --start <YYYY-MM-DD> --end <YYYY-MM-DD>` is executed
- **THEN** theme analysis SHALL run for the provided date range
- **AND** discovered themes SHALL be displayed with names and related content counts

#### Scenario: Analyze themes with default range
- **WHEN** `aca analyze themes` is executed without `--start` or `--end`
- **THEN** theme analysis SHALL run for the last 7 days
- **AND** discovered themes SHALL be displayed

### Requirement: Graph subcommands
The system SHALL provide `aca graph` subcommands for knowledge graph workflows.

#### Scenario: Extract entities
- **WHEN** `aca graph extract-entities --content-id <id>` is executed
- **THEN** named entities SHALL be extracted from the specified content
- **AND** entities SHALL be stored in the knowledge graph

#### Scenario: Query knowledge graph
- **WHEN** `aca graph query --query <text>` is executed
- **THEN** the knowledge graph SHALL be queried
- **AND** matching entities and relationships SHALL be displayed

#### Scenario: Graph unavailable
- **GIVEN** Neo4j is not running or not configured
- **WHEN** `aca graph query --query "AI"` is executed
- **THEN** an error message SHALL indicate the graph database is unavailable
- **AND** exit code SHALL be 1

### Requirement: Podcast subcommands
The system SHALL provide `aca podcast` subcommands for podcast generation workflows.

#### Scenario: Generate podcast from digest
- **WHEN** `aca podcast generate --digest-id <id>` is executed
- **THEN** a podcast script SHALL be generated from the specified digest
- **AND** the script id SHALL be displayed on success

#### Scenario: List podcast scripts
- **WHEN** `aca podcast list-scripts --limit <N>` is executed
- **THEN** recent podcast scripts SHALL be listed with id, digest title, and creation date

### Requirement: Manage subcommands
The system SHALL provide `aca manage` subcommands for setup and operational tasks.

#### Scenario: Setup Gmail OAuth
- **WHEN** `aca manage setup-gmail` is executed
- **THEN** the Gmail OAuth setup flow SHALL be initiated
- **AND** instructions SHALL guide the user through credential creation

#### Scenario: Verify setup
- **WHEN** `aca manage verify-setup` is executed
- **THEN** connectivity checks SHALL run for: database, Redis, Neo4j, LLM API
- **AND** each check SHALL show pass/fail status

#### Scenario: Railway sync
- **WHEN** `aca manage railway-sync` is executed
- **THEN** Railway deployment synchronization SHALL be triggered

#### Scenario: Check profile secrets
- **WHEN** `aca manage check-profile-secrets` is executed
- **THEN** the active profile SHALL be inspected for unresolved `${VAR}` references
- **AND** any missing secrets SHALL be listed as warnings

### Requirement: Backward compatibility
Legacy entrypoints SHALL continue to work but emit deprecation warnings.

#### Scenario: Legacy newsletter-cli alias
- **WHEN** `newsletter-cli profile list` is executed
- **THEN** the command SHALL work identically to `aca profile list`
- **AND** a deprecation warning SHALL be emitted to stderr recommending `aca profile`

#### Scenario: Legacy module entrypoint
- **WHEN** `python -m src.ingestion.gmail` is executed
- **THEN** the ingestion SHALL run (backward-compatible)
- **AND** a deprecation warning SHALL be emitted recommending `aca ingest gmail`

### Requirement: CLI and API parity
CLI command handlers SHALL call the same workflow services as API endpoints.

#### Scenario: Shared workflow services
- **GIVEN** a CLI command and API endpoint for the same workflow
- **WHEN** both are invoked with equivalent inputs
- **THEN** they SHALL use the same underlying service function
- **AND** the CLI SHALL use sync adapters (via `asyncio.run()`) to call async services
