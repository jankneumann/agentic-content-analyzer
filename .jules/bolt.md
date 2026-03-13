## 2026-03-03 - N+1 Optimization in Podcast Statistics
**Learning:** The `get_podcast_statistics` endpoint was performing O(N) database queries due to iterating over enums and running separate `COUNT` queries for each status and provider.
**Action:** Replaced iterative counts with `GROUP BY` aggregations. Used `func.count(Model.id)` grouped by the status/provider columns to fetch all counts in a single query per category. This reduced the operation from ~9 queries to 3 constant-time queries regardless of enum size.

## 2026-03-03 - SQLite Testing Limitations with JSONB
**Learning:** The test suite struggles with SQLite when using PostgreSQL-specific types like `JSONB`, even with monkeypatching. Models imported before the patch (like via `conftest.py` imports) retain the original type, causing `CompileError`.
**Action:** For future testing improvements, ensure all SQLAlchemy model imports in `conftest.py` happen *inside* fixtures or functions where the monkeypatch has already been applied, or use a robust `pytest_configure` hook to patch types globally before any app imports.

## 2026-01-26 - Missing Foreign Key Index on Self-Referential Relationship
**Learning:** The `canonical_id` self-referential foreign key in `Content` model was missing an index, causing potential performance issues during deduplication checks and deletion (cascading updates).
**Action:** Ensure all Foreign Keys, especially those used in filtering or joins (like self-referential ones), have `index=True` or an explicit index defined.

## 2026-02-04 - Inefficient `NOT IN` Set Lookup in Summarization Trigger
**Learning:** The summarization trigger was fetching ALL existing summary IDs into memory to filter out content that already has summaries. This scales poorly as the number of summaries grows.
**Action:** Replaced with a `LEFT JOIN` on `Summary` where `Summary.id IS NULL` to handle the filtering at the database level efficiently.

## 2026-02-09 - Deferring Heavy Columns in Bulk Operations
**Learning:** `Content` model has very large text/JSON columns (`markdown_content`, `tables_json`). When fetching bulk records for processing (e.g., triggering summarization), failure to `defer()` these columns can cause significant memory and time overhead, even if only IDs are needed.
**Action:** Always use `defer()` on heavy columns when fetching `Content` objects for background tasks or ID-only operations.

## 2026-02-12 - Fetching Full ORM Objects for Navigation
**Learning:** The `get_summary_navigation` endpoint was fetching full `Summary` and `Content` objects (thousands of them) into memory just to extract IDs for calculating prev/next links. This is O(N) in memory and time.
**Action:** Use explicit column selection `db.query(Summary.id, Summary.content_id)` to fetch only the necessary data as tuples, avoiding ORM object overhead and loading large text fields.

## 2026-02-14 - Optimize Search Preview Fetch
**Learning:** The search endpoint was fetching the full `chunk_text` for every result candidate, only to truncate it to 500 characters in Python for the preview. For large documents, this wasted significant database I/O and memory.
**Action:** Use `substr(column, 1, 500)` in the SQL query to perform the truncation at the database level.

## 2026-02-15 - Explicit Column Selection for List Views
**Learning:** Even with `defer()`, `db.query(Content)` hydrates full ORM objects which adds significant overhead (~38% slower) compared to explicitly selecting only the required columns for list views.
**Action:** Prefer `db.query(Model.col1, Model.col2)` over `db.query(Model).options(defer(...))` when fetching data for list endpoints where only a subset of fields is needed.

## 2026-02-15 - Redundant COUNT Queries
**Learning:** The statistics endpoint was running a separate `COUNT(*)` query for the total, followed by a `GROUP BY status` query. Since `status` is non-nullable, the sum of the group counts equals the total count. Eliminating the explicit count query saves a full index/table scan.
**Action:** When calculating statistics, derive the total count from the sum of categorical group counts (if the category column is mandatory) instead of running a separate query.

## 2026-02-27 - Caching Heavy Service Providers
**Learning:** Service providers like `LocalEmbeddingProvider` were being re-instantiated on every request (via `get_embedding_provider`). This caused heavy ML models (SentenceTransformers) to be reloaded from disk/cache repeatedly, adding seconds of latency to search and ingestion operations.
**Action:** Use `functools.lru_cache` for factory functions that create heavy or stateful service providers, ensuring they are initialized only once per configuration.

## 2024-05-19 - Single query optimization for API statistics
**Learning:** Found N+1 query patterns when grouping counts by different statuses and types in statistics API routes. By using `func.count()` with `group_by()` on the required columns and summing up the results in Python, we can drastically reduce DB queries (e.g. from 9 down to 1 query).
**Action:** When calculating statistics across multiple statuses or types, always look for opportunities to compute the counts programmatically using a single `GROUP BY` query, avoiding looping or multiple DB calls.

## 2026-03-04 - Optimize audio digest statistics query
**Learning:** Multiple separate database count queries were executed to aggregate counts (total, and individual status counts) in `get_audio_digest_statistics` which causes performance bottlenecks via redundant database round-trips.
**Action:** When calculating statistics that encompass the whole table partitioned by a specific property (like status), execute a single query using `func.count()` alongside `GROUP BY`, and compute derived values (like the total count or specific status values) within the application logic. This pattern minimizes the DB connection overhead.

## 2026-03-05 - N+1 Optimization in Audio Digest and Podcast Statistics
**Learning:** The `get_audio_digest_statistics` and `get_podcast_statistics` endpoints were executing separate `COUNT` and `SUM` queries for each grouping (e.g., status, voice, provider, duration sum). This led to 4 round-trips for audio digests and 3 for podcasts, creating unneeded overhead.
**Action:** When calculating stats across multiple attributes in the same table, consolidate them into a single query using `db.query(..., func.count(...), func.sum(...)).group_by(...)` and aggregate the marginal totals in Python. This reduces multiple O(N) database queries into a single constant-time query.
