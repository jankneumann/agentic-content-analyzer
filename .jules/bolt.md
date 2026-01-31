## 2026-01-20 - Missing Timestamp Indexes
**Learning:** Core timestamp columns like `created_at` or `ingested_at` were missing database indexes despite being used frequently in `order_by` clauses for feed generation.
**Action:** Always verify indexes on columns used for sorting or filtering, especially in core content tables. Use `sqlalchemy.inspect` or check `__table__.indexes` in tests to prevent regression.

## 2026-01-26 - Duplicate Alembic Revisions
**Learning:** Found duplicate revision ID `f1a2b3c4d5e6` used by both `add_pgqueuer_jobs_table.py` and `remove_redundant_indexes.py`, causing dependency graph conflicts. This likely happened due to parallel development.
**Action:** When adding migrations, always check `alembic heads` or list existing versions to avoid ID collisions. If a collision is found in existing files, one must be renamed and its ID updated to restore a valid graph.
