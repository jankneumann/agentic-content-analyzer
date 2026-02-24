# Content Ingestion: Grok X Search

## ADDED Requirements

### Requirement: X Post Ingestion via Grok API

The system SHALL support ingestion of X (Twitter) posts using the xAI Grok API's `x_search` tool for AI-relevant content discovery.

#### Scenario: Successful X thread search and ingestion

- **WHEN** the user runs the X search ingestion with a valid API key and search prompt
- **THEN** the system connects to xAI Grok API using `grok-4-1-fast` model
- **AND** executes the `x_search` tool with the provided prompt
- **AND** for each discovered post, fetches the complete thread if applicable
- **AND** creates one Content record per thread (or single post) with `source_type=xsearch`
- **AND** uses root_post_id as source_id for stable thread identification
- **AND** stores the complete thread in markdown_content with numbered sections
- **AND** stores structured metadata in metadata_json including root_post_id, thread_post_ids array, author info, and engagement metrics
- **AND** returns the count of newly ingested threads

#### Scenario: Thread-aware deduplication by root post ID

- **WHEN** ingesting a thread whose root_post_id already exists as source_id in the database
- **THEN** the system skips the duplicate thread without creating new records
- **AND** logs a debug message indicating the duplicate was skipped
- **AND** does not count duplicates in the ingestion count

#### Scenario: Thread-aware deduplication by thread member post ID

- **WHEN** ingesting a post that belongs to a thread already stored in the database
- **AND** the post's ID exists in the thread_post_ids array of an existing Content record
- **THEN** the system recognizes this as a duplicate thread
- **AND** skips without creating new records
- **AND** logs a debug message indicating the thread was already ingested via a different post

#### Scenario: Force reprocessing of existing threads

- **WHEN** the user specifies the force reprocess flag
- **THEN** the system updates existing Content records with fresh thread data
- **AND** resets the status to PARSED for re-summarization
- **AND** counts reprocessed threads in the ingestion count

#### Scenario: API authentication failure

- **WHEN** the xAI API key is missing or invalid
- **THEN** the system raises an authentication error with a descriptive message
- **AND** does not create any Content records
- **AND** logs the authentication failure

#### Scenario: Rate limiting by xAI API

- **WHEN** the xAI API returns a rate limit error
- **THEN** the system implements exponential backoff with retries
- **AND** respects the retry-after header if provided
- **AND** logs the rate limit event

### Requirement: Configurable X Search Prompts

The system SHALL support configurable prompts for guiding Grok's X search behavior.

#### Scenario: Using default search prompt

- **WHEN** no custom prompt is provided
- **THEN** the system uses the configured default prompt from GROK_X_SEARCH_PROMPT setting
- **AND** the default prompt focuses on AI research, model releases, and technical discussions

#### Scenario: Using custom search prompt

- **WHEN** the user provides a custom search prompt
- **THEN** the system uses the custom prompt for the Grok x_search tool
- **AND** stores the search query in metadata_json for traceability

### Requirement: X Search Cost Control

The system SHALL provide configuration options to control xAI API costs.

#### Scenario: Limiting tool call turns

- **WHEN** GROK_X_MAX_TURNS is configured
- **THEN** the system limits the number of agentic tool calling turns to the configured value
- **AND** Grok generates a response with available information when the limit is reached

#### Scenario: Limiting maximum threads

- **WHEN** GROK_X_MAX_THREADS is configured
- **THEN** the system stops processing after ingesting the configured maximum threads
- **AND** logs the limit was reached

#### Scenario: Cost tracking in metadata

- **WHEN** X posts are ingested
- **THEN** the system records the number of tool calls made in metadata_json
- **AND** includes estimated cost based on xAI pricing ($5 per 1000 tool calls)

### Requirement: X Post Content Formatting

The system SHALL format X posts as markdown content suitable for LLM summarization.

#### Scenario: Single post formatting

- **WHEN** a single X post is ingested
- **THEN** the markdown_content includes the author handle as header
- **AND** includes the post timestamp in human-readable format
- **AND** includes engagement metrics (likes, retweets, replies)
- **AND** includes the full post text
- **AND** includes links to any attached media
- **AND** includes a link back to the original post on X

#### Scenario: Thread formatting

- **WHEN** an X thread (multiple connected posts) is ingested
- **THEN** the system combines all thread posts into a single Content record
- **AND** uses the root (first) post ID as source_id
- **AND** stores all post IDs in metadata_json.thread_post_ids array for deduplication
- **AND** indicates thread_length in metadata_json
- **AND** formats the markdown with numbered sections (e.g., "### 1/5", "### 2/5") for each post in the thread
- **AND** the complete thread is passed to the summarizer as a single unit

### Requirement: X Search CLI Interface

The system SHALL provide a command-line interface for X post ingestion.

#### Scenario: Running X search from command line

- **WHEN** the user runs `python -m src.ingestion.xsearch`
- **THEN** the system executes X search with default configuration
- **AND** outputs progress information during search
- **AND** outputs summary statistics on completion (posts found, ingested, duplicates)

#### Scenario: CLI with custom options

- **WHEN** the user provides CLI arguments (--prompt, --max-threads, --force)
- **THEN** the system uses the provided options for the ingestion run
- **AND** validates argument values before execution
