# Review of Supabase Cloud Database Design

The design document `openspec/changes/add-supabase-cloud-database/design.md` provides a solid foundation for integrating Supabase as a first-class database provider. The proposed changes are well-structured, backward-compatible, and address the specific technical requirements of Supabase (connection pooling, SSL, etc.).

Below is a detailed review of the design.

## Strengths

1.  **Provider Pattern Abstraction**: The decision to introduce a `DatabaseProvider` protocol (`Decision 1`) is excellent. It decouples the database configuration logic from the core application, making it easier to add other providers (e.g., AWS RDS, Neon) in the future without modifying `src/storage/database.py`.
2.  **Supabase-Specific Configuration**: The design correctly identifies the critical differences between standard Postgres and Supabase's managed offering:
    *   **Port differentiation**: Distinguishing between Transaction Mode (6543) and Session Mode (5432) is crucial for Supavisor.
    *   **SSL Requirement**: Explicitly adding `sslmode: require` in `connect_args`.
    *   **Connection Pooling**: Tuning `pool_size` and `max_overflow` to respect Supabase's free tier limits is a thoughtful detail that will prevent user frustration.
3.  **Automatic Detection**: The logic to auto-detect Supabase based on environment variables (`SUPABASE_PROJECT_REF` or `.supabase.` in URL) simplifies the UX for new users.
4.  **Backward Compatibility**: The design ensures that existing local Postgres setups continue to work without changes.

## Considerations & Recommendations

### 1. Database Driver & Async Support
*   **Current State**: The project uses `psycopg2-binary` (Synchronous) with `SQLAlchemy`.
*   **Observation**: Since the application is built on **FastAPI**, using synchronous database drivers blocks the event loop unless explicitly handled (though FastAPI does run dependencies in a threadpool).
*   **Recommendation**: While the design maintains consistency with the current synchronous implementation (which is the correct scope for *this* specific change), it's worth noting that high-concurrency performance on Supabase might eventually benefit from an async driver like `asyncpg`. For now, the proposed synchronous design is acceptable and minimizes refactoring.

### 2. Alembic Migrations
*   **Issue**: The design mentions using the "Direct connection" for migrations (`Decision 5`).
*   **Gap**: It's not fully clear *how* Alembic will be configured to use this direct URL automatically. `alembic/env.py` typically reads `settings.database_url`.
*   **Recommendation**:
    *   Ensure `src/config/settings.py` includes a `get_migration_url()` method (or similar) on the `Settings` or `DatabaseProvider` class.
    *   Update `alembic/env.py` to prefer the direct URL (port 5432) over the pooled URL (port 6543) to avoid transaction mode issues during DDL operations.
    *   Add a `supabase_direct_url` field (computed or explicit) to the settings model.

### 3. Prepared Statements in Transaction Mode
*   **Risk**: Supavisor in Transaction Mode (port 6543) can sometimes have issues with prepared statements if not configured correctly on the Supabase side, or if the client tries to use named cursors.
*   **Mitigation**: The design sets `pool_pre_ping=True`, which is good. If users encounter "prepared statement does not exist" errors, the fallback is to use Session Mode (port 5432) or disable prepared statements in `psycopg2`. The design's default to Transaction Mode is correct for performance, but documentation should note how to switch to Session Mode if issues arise.

### 4. Statement Timeout
*   **Observation**: The design sets `statement_timeout=30000` (30s).
*   **Recommendation**: Ensure this aligns with the application's longest expected query (e.g., complex vector searches or aggregations). 30s is generally safe but might be tight for heavy analytical queries if those exist.

### 5. Dependency Management
*   **Observation**: `psycopg2-binary` is already in `pyproject.toml`.
*   **Recommendation**: No new dependencies are strictly required, which is good.

## Implementation Roadmap Verification

The proposed file structure is logical:
```
src/storage/
├── providers/
│   ├── base.py
│   ├── local.py
│   ├── supabase.py
│   └── factory.py
└── database.py
```

This structure separates concerns effectively.

## Conclusion

**Status: Approved with minor suggestions.**

The design is well-thought-out and ready for implementation. The primary recommendation is to ensure the **Alembic migration path** is robustly handled in code (e.g., via `alembic/env.py` modification) so users don't have to manually toggle environment variables to run migrations.
