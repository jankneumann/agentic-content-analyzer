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
All CLI commands SHALL use Rich console output by default for human-readable
display. When JSON output is requested, stdout MUST contain exactly one valid
JSON document and diagnostics MUST be written to stderr.

#### Scenario: Default Rich output
- **WHEN** any `aca` command is executed without `--json`
- **THEN** output SHALL be formatted using Rich tables, panels, or styled text

#### Scenario: JSON output
- **WHEN** any `aca` command is executed with `--json`
- **THEN** output SHALL be valid JSON printed to stdout
- **AND** progress messages SHALL be suppressed or sent to stderr
- **AND** no human-readable prefix or warning SHALL precede the JSON document

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

#### Scenario: Switch embedding provider
- **WHEN** `aca manage switch-embeddings --provider <name> --model <model> [--batch-size N] [--delay N] [--skip-backfill] [--dry-run] [--yes]` is executed
- **THEN** the system validates the target provider/model, clears existing embeddings, rebuilds the HNSW index, and optionally triggers backfill
- **AND** a summary of cleared and regenerated embeddings SHALL be displayed
- **AND** confirmation SHALL be required unless `--yes` is provided

#### Scenario: Backfill chunks
- **WHEN** `aca manage backfill-chunks [--batch-size N] [--delay N] [--dry-run] [--embed-only] [--content-id N]` is executed
- **THEN** existing content without chunks SHALL be chunked and embedded
- **AND** a summary of processed content, created chunks, and generated embeddings SHALL be displayed

### Requirement: CLI and API parity

CLI workflow commands and HTTP endpoints SHALL construct the same typed application commands and submit them through the same job-backed application workflow services. Equivalent normalized inputs MUST produce the same operation type, validation behavior, idempotency semantics, and final resource contract.

#### Scenario: Shared job-backed ingestion service
- **GIVEN** a CLI command and HTTP request for the same ingestion source
- **WHEN** both are invoked with equivalent inputs
- **THEN** both submit the same discriminated ingestion command
- **AND** both execute through `IngestionService` in a PostgreSQL worker
- **AND** no source option is lost in either transport
- **AND** URL auto-routing and forced-webpage mode produce equivalent normalized queue payloads

#### Scenario: Adding a new ingestion source
- **WHEN** a new source descriptor and fixture are added
- **THEN** generated CLI and HTTP contracts expose that source
- **AND** no transport-specific dispatcher is added

### Requirement: Ingestion orchestrator module
The system SHALL provide orchestrator functions in `src/ingestion/orchestrator.py` that encapsulate service instantiation and invocation for each ingestion source (gmail, rss, youtube, podcast, substack).

#### Scenario: Orchestrator function contract
- **WHEN** an orchestrator function is called (e.g., `ingest_gmail()`, `ingest_rss()`)
- **THEN** it SHALL import the required service classes lazily (inside the function body)
- **AND** it SHALL instantiate the services, call the appropriate methods, and return `int` (items ingested)
- **AND** source-specific constructor arguments (e.g., `use_oauth`, `session_cookie`) SHALL be accepted as keyword parameters

#### Scenario: YouTube orchestrator encapsulates multi-service pattern
- **WHEN** `ingest_youtube()` is called
- **THEN** it SHALL call `YouTubeContentIngestionService.ingest_all_playlists()`, `YouTubeContentIngestionService.ingest_channels()`, and `YouTubeRSSIngestionService.ingest_all_feeds()`
- **AND** it SHALL return the sum of all three counts

#### Scenario: RSS orchestrator with optional result callback
- **WHEN** `ingest_rss(on_result=callback)` is called
- **THEN** the callback SHALL receive the full `IngestionResult` object (including `failed_sources` and `redirected_sources`)
- **AND** the function SHALL still return `int` (items ingested)

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

### Requirement: Legacy jobs history is not a canonical CLI surface

The CLI SHALL expose durable work through `aca operations` and terminal
ingestion audit rows through `aca ingest history`. It SHALL NOT reintroduce the
retired `aca jobs history` command as a second workflow history contract.

#### Scenario: Operator needs general workflow state
- **WHEN** an operator needs queued, active, or terminal workflow state
- **THEN** the operator uses the bounded `aca operations list` surface
- **AND** exact results remain available from `aca operations get <id>`

#### Scenario: Operator needs ingestion outcomes
- **WHEN** an operator needs command, configured-source, outcome, lifecycle, parent, or creation-window filters
- **THEN** the operator uses `aca ingest history`
- **AND** no compatibility job-history alias is required

### Requirement: CLI reconciles one bounded content page remotely

The CLI SHALL expose `aca operations reconcile-content` as a remote-only,
dry-run-by-default command with explicit `--apply`, `--limit`, and
`--after-content-id` controls.

#### Scenario: Operator previews one page
- **WHEN** the command is invoked without `--apply`
- **THEN** it requests one dry-run page and exits zero after rendering it

#### Scenario: Operator applies one page
- **WHEN** `--apply` is supplied
- **THEN** the CLI requests one enabled apply page through `WorkflowApiClient`
- **AND** it does not connect directly to the application database

#### Scenario: Apply is disabled
- **WHEN** the server returns the apply-disabled RFC 7807 problem
- **THEN** the CLI renders the safe problem and exits nonzero

### Requirement: Prompt Management CLI Commands

The system SHALL provide `aca prompts` subcommands for managing LLM prompt configuration from the command line.

#### Scenario: List all prompts
- **WHEN** `aca prompts list` is executed
- **THEN** all prompts SHALL be displayed grouped by category (chat, pipeline)
- **AND** each prompt SHALL show: key, category, name, whether it has an override
- **AND** overridden prompts SHALL be visually distinguished (e.g., badge or color)

#### Scenario: List prompts filtered by category
- **WHEN** `aca prompts list --category pipeline` is executed
- **THEN** only pipeline prompts SHALL be displayed
- **AND** chat prompts SHALL be excluded

#### Scenario: Show a specific prompt
- **WHEN** `aca prompts show pipeline.summarization.system` is executed
- **THEN** the full prompt text SHALL be displayed
- **AND** if an override exists, both the override and default SHALL be shown
- **AND** the prompt version number SHALL be displayed

#### Scenario: Set a prompt override
- **WHEN** `aca prompts set pipeline.summarization.system --value "New prompt text"` is executed
- **THEN** the prompt override SHALL be stored in the database
- **AND** a confirmation message SHALL be displayed with the new value preview

#### Scenario: Set a prompt override from file
- **WHEN** `aca prompts set pipeline.summarization.system --file prompt.txt` is executed
- **THEN** the prompt text SHALL be read from the specified file
- **AND** the prompt override SHALL be stored in the database

#### Scenario: Reset a prompt to default
- **WHEN** `aca prompts reset pipeline.summarization.system` is executed
- **THEN** the database override SHALL be deleted
- **AND** a confirmation SHALL show the prompt will revert to the YAML default

#### Scenario: Export all prompts
- **WHEN** `aca prompts export --output prompts-backup.yaml` is executed
- **THEN** all current prompt values (including overrides) SHALL be written to the specified YAML file
- **AND** the file format SHALL match the `prompts.yaml` structure

#### Scenario: Import prompts
- **WHEN** `aca prompts import --file prompts-backup.yaml` is executed
- **THEN** prompts from the file SHALL be loaded as database overrides
- **AND** a confirmation SHALL show how many prompts were imported
- **AND** existing overrides SHALL be updated, not duplicated

#### Scenario: Test a prompt
- **WHEN** `aca prompts test pipeline.summarization.system` is executed
- **THEN** the prompt SHALL be rendered with sample content (most recent or specified via `--content-id`)
- **AND** the rendered prompt SHALL be sent to the LLM
- **AND** the LLM response text and token usage SHALL be displayed
- **AND** no pipeline artifacts SHALL be persisted

#### Scenario: Test a prompt with specific content
- **WHEN** `aca prompts test pipeline.summarization.system --content-id 42` is executed
- **THEN** content item 42 SHALL be used as sample input for the test

#### Scenario: Invalid prompt key
- **WHEN** `aca prompts show nonexistent.key` is executed
- **THEN** an error message SHALL indicate the prompt key is not recognized
- **AND** available keys SHALL be suggested

### Requirement: Durable CLI workflow behavior

Every long-running CLI workflow command SHALL submit an operation. Human output SHALL display operation and resource IDs; `--json` SHALL emit the canonical schema; `--wait` SHALL observe the operation until terminal status; and `--no-wait` SHALL return after durable submission.

#### Scenario: CLI waits for digest resource
- **WHEN** `aca digest create ... --wait --json` succeeds
- **THEN** stdout contains the completed operation handle and persisted digest resource reference
- **AND** progress output does not corrupt JSON stdout

#### Scenario: CLI returns queued operation
- **WHEN** a workflow command uses `--no-wait`
- **THEN** it exits successfully after returning a queryable queued operation ID

### Requirement: CLI capability discovery

The CLI SHALL provide `aca capabilities` and `aca configured-sources` with
human-readable and JSON output derived from canonical cursor-page documents.
Optional query parameters that are absent MUST NOT be serialized into the HTTP
request.

#### Scenario: Agent discovers source command fields
- **WHEN** `aca capabilities --json` is executed
- **THEN** the result lists every canonical ingestion discriminator and its accepted fields
- **AND** it lists supported operation and resource types

#### Scenario: Configured sources use command-local JSON

- **WHEN** `aca configured-sources --json` is executed
- **THEN** stdout contains exactly one configured-source page JSON document
- **AND** the command exits successfully

#### Scenario: First discovery page omits cursor

- **WHEN** capabilities, configured sources, or operations are listed without a cursor
- **THEN** the serialized HTTP query contains the requested limit
- **AND** the serialized HTTP query does not contain a `cursor` key

#### Scenario: Explicit cursor is preserved

- **WHEN** a caller supplies an opaque cursor to a discovery or operation-list request
- **THEN** the serialized HTTP query contains that exact cursor value
- **AND** pagination continues through the canonical endpoint

### Requirement: Gemini batch operator commands

The CLI SHALL expose read-only `batch status` and SHALL support canonical root
`--json` output without stray human-readable text.

#### Scenario: JSON batch status is machine readable

- **WHEN** a user runs `aca --json batch status`
- **THEN** stdout SHALL contain exactly one valid JSON document

### Requirement: Canonical ingestion history CLI

The CLI SHALL expose `aca ingest history` as the operation-derived terminal
ingestion history surface. It SHALL support command key, opaque configured-source
key, domain outcome, terminal lifecycle status, parent operation, created-after,
created-before, limit, and signed cursor filters equivalent to
`GET /api/v1/ingestions`.

#### Scenario: Filtered ingestion history is requested
- **WHEN** a caller supplies `--command-key rss --outcome partial --status completed`
- **THEN** every returned row satisfies all supplied filters
- **AND** each row is compact and contains no full result, checkpoint, content-ID array, or natural source locator

#### Scenario: Every history page is traversed
- **WHEN** a caller uses `aca ingest history --all`
- **THEN** traversal stops at the validated `--max-pages` budget
- **AND** the default is 20 pages of at most 100 rows each
- **AND** exhaustion exposes `truncated=true` and a continuation cursor in JSON or a human stderr warning

#### Scenario: History JSON mode has no matches
- **WHEN** filtered history contains zero rows and JSON output is requested
- **THEN** stdout contains exactly one page document with `data=[]`
- **AND** the command exits zero

#### Scenario: Optional filters are absent
- **WHEN** an unfiltered first history page is requested
- **THEN** absent optional values are omitted from the serialized HTTP query
- **AND** no empty cursor value is sent

### Requirement: Pipeline wait reports ingestion outcome

Waiting pipeline commands SHALL preserve JSON stdout purity while reporting
domain-level partial and zero-item outcomes.

#### Scenario: Tolerated partial pipeline completes
- **WHEN** a pipeline completes with `ingestion_summary.outcome=partial` and continuation is enabled
- **THEN** the CLI exits zero and writes a warning to stderr
- **AND** JSON stdout contains the partial outcome without additional text

#### Scenario: Pipeline succeeds with zero items
- **WHEN** a completed pipeline has `ingestion_summary.outcome=zero_items`
- **THEN** human output reports that no items were ingested
- **AND** the CLI exit code remains zero

### Requirement: Backup Command Group

The CLI SHALL expose an `aca backup` command group providing scheduled-backup
execution, prerequisite verification, and backup listing, following the
established CLI output contract.

#### Scenario: Backup command group is discoverable
- **GIVEN** the CLI is installed
- **WHEN** `aca backup --help` is invoked
- **THEN** `run`, `verify`, and `list` subcommands SHALL be listed

#### Scenario: Backup commands honor the JSON output contract
- **GIVEN** the CLI is invoked in JSON mode
- **WHEN** any `aca backup` subcommand completes
- **THEN** stdout SHALL contain exactly one JSON document
- **AND** all logging and diagnostics SHALL be written to stderr

#### Scenario: Backup output never contains credentials
- **GIVEN** any `aca backup` subcommand result in either output mode
- **WHEN** the output is inspected
- **THEN** it SHALL NOT contain access keys, secret keys, or any URL embedding credentials

#### Scenario: Listing backups does not mutate the target
- **GIVEN** `aca backup list` is invoked
- **WHEN** it completes
- **THEN** it SHALL perform only read operations against the backup target

### Requirement: Restore From Cloud Command

The CLI SHALL provide `aca manage restore-from-cloud` to retrieve a backup from
the configured backup target and replay it into a target database. The command
SHALL operate against any S3-compatible backup target, SHALL NOT expose
credentials in its arguments or output, and SHALL retain its safeguards against
restoring over a live remote database.

#### Scenario: Restore works against any S3-compatible target
- **GIVEN** the backup target is Cloudflare R2, AWS S3, or MinIO
- **WHEN** `aca manage restore-from-cloud` is invoked
- **THEN** the same code path SHALL be used for each
- **AND** the target SHALL be resolved from the provider-neutral backup settings

#### Scenario: Backup artifacts are discovered independently of legacy naming
- **GIVEN** backup artifacts stored under the configured prefix
- **WHEN** the command lists available backups
- **THEN** artifacts SHALL be discovered by the configured prefix and timestamp convention
- **AND** discovery SHALL NOT depend on a `railway-` filename prefix

#### Scenario: Credentials are not passed as process arguments
- **GIVEN** the command invokes an external storage client
- **WHEN** the subprocess is constructed
- **THEN** access keys and secret keys SHALL NOT appear in the process argument list

#### Scenario: Command output masks the target database credentials
- **GIVEN** the command completes successfully in JSON mode
- **WHEN** the emitted document is inspected
- **THEN** the reported target database SHALL have its credentials masked

#### Scenario: Encrypted artifacts are decrypted during restore
- **GIVEN** a backup artifact encrypted with the configured recipient
- **WHEN** the command retrieves it
- **THEN** it SHALL be decrypted using the configured identity before replay
- **AND** GIVEN no identity is available, the command SHALL abort naming the missing identity

#### Scenario: Live database safeguard resists URL variation
- **GIVEN** a requested target database URL that addresses the same database as the configured remote database URL but differs in textual form
- **WHEN** the command resolves the restore target
- **THEN** the command SHALL refuse the restore
- **AND** the refusal SHALL name the explicit opt-in flag required to override it

#### Scenario: Destructive restore safeguards are retained
- **GIVEN** a restore that will drop and recreate schema objects in the target
- **WHEN** the command runs without an explicit confirmation flag in interactive mode
- **THEN** it SHALL require confirmation before proceeding

