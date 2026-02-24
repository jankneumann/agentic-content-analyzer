# Tasks: Grok API X News Search Integration

## 1. Dependencies and Configuration

- [x] 1.1 Add `xai-sdk>=1.3.1` to project dependencies (pyproject.toml)
- [x] 1.2 Add configuration settings to `src/config/settings.py`:
  - `XAI_API_KEY`: API key for xAI Grok
  - `GROK_MODEL`: Model to use (default: `grok-4-1-fast`)
  - `GROK_X_SEARCH_PROMPT`: Default search prompt template
  - `GROK_X_MAX_TURNS`: Max tool calling turns (default: 5)
  - `GROK_X_MAX_THREADS`: Max threads per search (default: 50)
- [x] 1.3 Document environment variables in `.env.example`

## 2. Database Schema

- [x] 2.1 Add `XSEARCH = "xsearch"` to `ContentSource` enum in `src/models/content.py`
- [x] 2.2 Create Alembic migration to add `xsearch` value to `content_source` enum type in PostgreSQL:
  ```sql
  ALTER TYPE content_source ADD VALUE 'xsearch';
  ```
- [x] 2.3 Run migration and verify enum update

## 3. Client Implementation

- [x] 3.1 Create `src/ingestion/xsearch.py` module
- [x] 3.2 Implement `GrokXClient` class:
  ```python
  class GrokXClient:
      """Client for searching X threads using Grok API."""

      def __init__(self, api_key: str | None = None, model: str = "grok-4-1-fast")
      def search_threads(self, prompt: str, max_turns: int = 5) -> list[XThreadData]
      def _fetch_complete_thread(self, post_id: str) -> XThreadData
      def _parse_response(self, response) -> list[XThreadData]
      def close(self) -> None
  ```
- [x] 3.3 Implement `XThreadData` Pydantic model for parsed thread data:
  ```python
  class XThreadData(BaseModel):
      root_post_id: str                    # First post ID (used as source_id)
      thread_post_ids: list[str]           # All post IDs in thread
      author_handle: str
      author_name: str
      posts: list[XPostContent]            # Ordered list of post contents
      posted_at: datetime
      is_thread: bool
      thread_length: int
      # ... engagement metrics, media, etc.
  ```
- [x] 3.4 Implement streaming response handling with tool call logging
- [x] 3.5 Add error handling for API failures, rate limits, authentication errors
- [x] 3.6 Add retry logic with exponential backoff
- [x] 3.7 Implement thread fetching: when a post is discovered, fetch its complete thread

## 4. Service Implementation

- [x] 4.1 Implement `GrokXContentIngestionService` class:
  ```python
  class GrokXContentIngestionService:
      """Service for ingesting X threads into the Content model."""

      def __init__(self)
      def ingest_threads(
          self,
          prompt: str | None = None,
          max_turns: int | None = None,
          max_threads: int | None = None,
          force_reprocess: bool = False,
      ) -> int
      def close(self) -> None
  ```
- [x] 4.2 Implement thread-to-ContentData conversion with markdown formatting:
  - Use root_post_id as source_id
  - Format thread posts with numbered sections (### 1/5, ### 2/5, etc.)
  - Store complete thread in markdown_content for summarization
- [x] 4.3 Implement thread-aware deduplication:
  - Primary: Check if root_post_id exists as source_id
  - Secondary: Query metadata_json to check if ANY incoming post_id exists in stored thread_post_ids arrays
  - Fallback: Content hash for edge cases
- [x] 4.4 Add cost tracking in metadata_json (tool calls made, estimated cost)

## 5. CLI Interface

- [x] 5.1 Add `xsearch` command to `src/cli/ingest_commands.py` with Typer:
  ```bash
  aca ingest xsearch                        # Use default/configured prompt
  aca ingest xsearch --prompt "..."         # Custom prompt
  aca ingest xsearch --max-threads 100      # Limit results
  aca ingest xsearch --force                # Reprocess existing
  ```
- [x] 5.2 Add `ingest_xsearch()` to `src/ingestion/orchestrator.py`
- [x] 5.3 Wire xsearch into `_run_ingestion_stage_async()` in `src/cli/pipeline_commands.py`

## 6. Testing

- [x] 6.1 Create `tests/test_ingestion/test_xsearch.py`
- [x] 6.2 Write unit tests for `XThreadData` model validation
- [x] 6.3 Write unit tests for thread markdown content generation (numbered sections)
- [x] 6.4 Write unit tests for thread-aware deduplication:
  - Dedupe by root_post_id (source_id match)
  - Dedupe by thread member post_id (found in thread_post_ids array)
  - Verify different posts from same thread don't create duplicate Content records
- [x] 6.5 Write integration tests with mocked xAI SDK responses
- [x] 6.6 Add test fixtures for sample thread data (single post, multi-post threads)

## 7. Documentation

- [x] 7.1 Update `CLAUDE.md` with X search commands and gotchas
- [x] 7.2 Add configurable prompt to `src/config/prompts.yaml` (pipeline.xsearch.search_prompt)
- [x] 7.3 Wire `XAI_API_KEY` into `profiles/base.yaml`

## 8. Integration Verification

- [ ] 8.1 Run end-to-end test with real Grok API (manual, requires API key)
- [ ] 8.2 Verify posts appear in Content table with correct structure
- [ ] 8.3 Verify posts flow through summarization pipeline
- [ ] 8.4 Verify posts appear in digest output

## Dependencies

- Task 2 depends on Task 1.1 (need xai-sdk installed)
- Task 3 depends on Task 1 (configuration needed)
- Task 4 depends on Tasks 2, 3 (schema and client needed)
- Task 5 depends on Task 4 (service needed)
- Task 6 depends on Tasks 3, 4 (implementation needed)
- Task 7 can run in parallel after Task 4
- Task 8 depends on all previous tasks
