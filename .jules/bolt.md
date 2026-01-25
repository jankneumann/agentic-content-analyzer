## 2026-01-20 - Missing Timestamp Indexes
**Learning:** Core timestamp columns like `created_at` or `ingested_at` were missing database indexes despite being used frequently in `order_by` clauses for feed generation.
**Action:** Always verify indexes on columns used for sorting or filtering, especially in core content tables. Use `sqlalchemy.inspect` or check `__table__.indexes` in tests to prevent regression.
