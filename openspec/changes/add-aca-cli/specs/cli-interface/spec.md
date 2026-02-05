## ADDED Requirements

### Requirement: aca CLI entrypoint
The system SHALL provide a top-level CLI command named `aca`.

#### Scenario: Display help
- **WHEN** `aca --help` is executed
- **THEN** a list of available subcommands SHALL be displayed

### Requirement: Ingest subcommands
The system SHALL provide `aca ingest` subcommands for supported ingestion sources.

#### Scenario: Ingest Gmail
- **WHEN** `aca ingest gmail --query <query> --max <count> --days <days> --force` is executed
- **THEN** Gmail ingestion SHALL run with the provided options

#### Scenario: Ingest RSS
- **WHEN** `aca ingest rss --feeds <url...> --max <count> --days <days> --force` is executed
- **THEN** RSS ingestion SHALL run with the provided options

### Requirement: Summarize subcommands
The system SHALL provide `aca summarize` subcommands for content summarization.

#### Scenario: Summarize pending content
- **WHEN** `aca summarize pending` is executed
- **THEN** all pending content SHALL be summarized

#### Scenario: Summarize by id
- **WHEN** `aca summarize id <content-id>` is executed
- **THEN** the specified content SHALL be summarized

### Requirement: Create digest subcommands
The system SHALL provide `aca create-digest` subcommands for daily and weekly digests.

#### Scenario: Create daily digest
- **WHEN** `aca create-digest daily --date <YYYY-MM-DD>` is executed
- **THEN** a daily digest SHALL be generated for that date

#### Scenario: Create weekly digest
- **WHEN** `aca create-digest weekly --week <YYYY-MM-DD>` is executed
- **THEN** a weekly digest SHALL be generated for the requested week

### Requirement: Pipeline subcommands
The system SHALL provide `aca pipeline` subcommands to run ingest → summarize → digest workflows.

#### Scenario: Run daily pipeline
- **WHEN** `aca pipeline daily --date <YYYY-MM-DD>` is executed
- **THEN** the daily pipeline SHALL ingest, summarize, and create a digest

### Requirement: Review and revise subcommands
The system SHALL provide `aca review` and `aca revise` commands for digest review workflows.

#### Scenario: List pending reviews
- **WHEN** `aca review list` is executed
- **THEN** pending digests SHALL be listed

#### Scenario: Revise digest
- **WHEN** `aca revise <digest-id>` is executed
- **THEN** an interactive revision session SHALL be started

### Requirement: Analyze subcommands
The system SHALL provide `aca analyze` subcommands for theme analysis.

#### Scenario: Analyze themes by date range
- **WHEN** `aca analyze themes --range <start> <end>` is executed
- **THEN** theme analysis SHALL run for the provided range

### Requirement: Graph subcommands
The system SHALL provide `aca graph` subcommands for knowledge graph workflows.

#### Scenario: Query knowledge graph
- **WHEN** `aca graph query --query <text>` is executed
- **THEN** the knowledge graph SHALL be queried and results displayed

### Requirement: Podcast subcommands
The system SHALL provide `aca podcast` subcommands for podcast generation workflows.

#### Scenario: Generate podcast from digest
- **WHEN** `aca podcast generate --digest-id <id>` is executed
- **THEN** a podcast script and audio generation workflow SHALL run

### Requirement: Manage subcommands
The system SHALL provide `aca manage` subcommands for setup and operations tasks.

#### Scenario: Verify setup
- **WHEN** `aca manage verify-setup` is executed
- **THEN** setup checks SHALL run and report status

### Requirement: CLI and API parity
CLI command handlers SHALL call the same workflow services as API endpoints.

#### Scenario: Shared workflow services
- **GIVEN** a CLI command and API endpoint for the same workflow
- **WHEN** both are invoked with equivalent inputs
- **THEN** they SHALL use the same underlying service function
