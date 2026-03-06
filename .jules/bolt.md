## 2026-03-03 - N+1 Optimization in Podcast Statistics
**Learning:** The `get_podcast_statistics` endpoint was performing O(N) database queries due to iterating over enums and running separate `COUNT` queries for each status and provider.
**Action:** Replaced iterative counts with `GROUP BY` aggregations. Used `func.count(Model.id)` grouped by the status/provider columns to fetch all counts in a single query per category. This reduced the operation from ~9 queries to 3 constant-time queries regardless of enum size.

## 2026-03-03 - SQLite Testing Limitations with JSONB
**Learning:** The test suite struggles with SQLite when using PostgreSQL-specific types like `JSONB`, even with monkeypatching. Models imported before the patch (like via `conftest.py` imports) retain the original type, causing `CompileError`.
**Action:** For future testing improvements, ensure all SQLAlchemy model imports in `conftest.py` happen *inside* fixtures or functions where the monkeypatch has already been applied, or use a robust `pytest_configure` hook to patch types globally before any app imports.

## $(date +%Y-%m-%d) - Optimize audio digest statistics query
**Learning:** Multiple separate database count queries were executed to aggregate counts (total, and individual status counts) in `get_audio_digest_statistics` which causes performance bottlenecks via redundant database round-trips.
**Action:** When calculating statistics that encompass the whole table partitioned by a specific property (like status), execute a single query using `func.count()` alongside `GROUP BY`, and compute derived values (like the total count or specific status values) within the application logic. This pattern minimizes the DB connection overhead.
