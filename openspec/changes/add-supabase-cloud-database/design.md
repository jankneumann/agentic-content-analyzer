# Design: Supabase Cloud Database Support

## Context

The newsletter aggregator currently requires local PostgreSQL via Docker Compose. This creates friction for new users and limits deployment flexibility. We want to support Supabase as a cloud alternative while maintaining backward compatibility.

**Reference Implementation**: [kbroose/stash](https://github.com/kbroose/stash) - A self-hosted app where users bring their own Supabase instance. Users create a free Supabase project, run the schema, and configure credentials.

## Goals

1. Support Supabase as a first-class database option
2. Abstract database provider selection from application code
3. Maintain 100% backward compatibility with local PostgreSQL
4. Enable "bring your own Supabase" for multi-user scenarios
5. Handle Supabase-specific features (connection pooling, SSL)

## Non-Goals

1. Supporting other cloud databases (RDS, Cloud SQL, etc.) in this change
2. Managing Supabase infrastructure (users provision their own)
3. Implementing Supabase Auth or other Supabase services
4. Multi-tenancy within a single Supabase instance

## Decisions

### Decision 1: Provider Abstraction Pattern

**What**: Create a `DatabaseProvider` protocol with implementations for each provider.

**Why**: Allows provider-specific configuration without polluting the core database module. Follows the same pattern as `DocumentParser` in the parsers module.

**Structure**:
```python
# src/storage/providers/base.py
class DatabaseProvider(Protocol):
    """Protocol for database providers."""

    @property
    def name(self) -> str: ...

    def get_engine_url(self) -> str: ...

    def get_engine_options(self) -> dict[str, Any]: ...

    def health_check(self, engine: Engine) -> bool: ...
```

### Decision 2: Automatic Provider Detection

**What**: Auto-detect provider from environment variables with explicit override option.

**Why**: Minimizes configuration for users while allowing explicit control when needed.

**Detection Order**:
1. Explicit `DATABASE_PROVIDER` env var (if set)
2. `SUPABASE_PROJECT_REF` env var present → Supabase provider
3. `DATABASE_URL` contains `.supabase.` → Supabase provider
4. Default → Local PostgreSQL provider

```python
# src/config/settings.py
@property
def database_provider(self) -> Literal["local", "supabase"]:
    if self.database_provider_override:
        return self.database_provider_override
    if self.supabase_project_ref:
        return "supabase"
    if ".supabase." in self.database_url:
        return "supabase"
    return "local"
```

### Decision 3: Supabase Connection Pooling via Supavisor

**What**: Support both transaction mode and session mode pooling.

**Why**: Supabase uses Supavisor for connection pooling. Transaction mode is more efficient but requires specific SQLAlchemy configuration.

**Connection String Formats**:
```
# Direct connection (no pooling, limited connections)
postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# Transaction pooling (recommended, port 6543)
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Session pooling (for prepared statements, port 5432)
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
```

**SQLAlchemy Configuration for Transaction Mode**:
```python
# Transaction mode requires these settings
engine_options = {
    "pool_pre_ping": True,
    "pool_size": 5,  # Limited due to Supabase free tier
    "max_overflow": 2,
    "pool_recycle": 300,  # 5 min recycle
    "connect_args": {
        "sslmode": "require",
        "options": "-c statement_timeout=30000",  # 30s timeout
    }
}
```

### Decision 4: URL Construction from Components

**What**: Allow users to configure Supabase via individual settings OR a complete URL.

**Why**: Individual settings are easier for users unfamiliar with PostgreSQL connection strings. Complete URL allows advanced users full control.

```python
# settings.py
def get_database_url(self) -> str:
    """Get database URL, constructing from Supabase config if needed."""
    if self.supabase_project_ref and self.supabase_db_password:
        # Construct Supabase pooler URL
        port = 6543 if self.supabase_pooler_mode == "transaction" else 5432
        return (
            f"postgresql://postgres.{self.supabase_project_ref}:"
            f"{self.supabase_db_password}@"
            f"aws-0-{self.supabase_region}.pooler.supabase.com:"
            f"{port}/postgres"
        )
    return self.database_url
```

### Decision 5: Schema Management with Alembic

**What**: Use existing Alembic migrations for both providers.

**Why**: Supabase supports standard PostgreSQL DDL. No changes needed to migration files.

**Considerations**:
- Supabase free tier has 500MB storage limit
- Users must grant Alembic connection access (not just pooler)
- Direct connection URL needed for migrations (bypasses pooler)

```bash
# For migrations, use direct URL (not pooler)
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres \
    alembic upgrade head
```

## Alternatives Considered

### Alternative A: Environment Variable Only (No Abstraction)

Just detect `.supabase.` in DATABASE_URL and apply different engine options.

**Rejected because**:
- Harder to add future providers
- Configuration logic scattered
- No clear place for provider-specific health checks

### Alternative B: Full ORM Abstraction (Repository Pattern)

Wrap all database access in repository classes that hide SQLAlchemy.

**Rejected because**:
- Over-engineering for the current need
- Services already provide adequate abstraction
- Would require massive refactor of existing code

### Alternative C: Supabase Python SDK

Use `supabase-py` library for database access.

**Rejected because**:
- Adds dependency on Supabase SDK
- Loses SQLAlchemy ORM features
- Would require rewriting all database code
- Supabase SDK is just a REST wrapper, not full PostgreSQL access

## Risks and Trade-offs

### Risk 1: Supabase Free Tier Limits
- **Risk**: Free tier limited to 500MB, 50 concurrent connections
- **Mitigation**: Document limits, recommend upgrade for production use

### Risk 2: Connection Pooling Complexity
- **Risk**: Transaction mode pooling has gotchas (no prepared statements, connection reset)
- **Mitigation**: Default to transaction mode with proper SQLAlchemy config, document session mode for edge cases

### Risk 3: Migration Complexity
- **Risk**: Users may try to run migrations through pooler
- **Mitigation**: Clear docs, separate `SUPABASE_DIRECT_URL` setting for migrations

### Risk 4: Region Latency
- **Risk**: Supabase region may be far from user's deployment
- **Mitigation**: Allow region configuration, recommend closest region

## Migration Plan

### Phase 1: Add Provider Abstraction (Non-Breaking)
1. Create provider module with factory
2. Refactor database.py to use factory
3. Existing DATABASE_URL continues working

### Phase 2: Add Supabase Configuration
1. Add Supabase settings to Settings class
2. Add URL construction logic
3. Test with Supabase free tier

### Phase 3: Documentation
1. Add Supabase setup guide
2. Document "bring your own Supabase" workflow
3. Add troubleshooting section

### Rollback
- Remove provider module
- Revert database.py changes
- No data migration needed

## Open Questions

1. **Q**: Should we support Supabase Auth for multi-user scenarios?
   **A**: Out of scope for this change. Future enhancement if needed.

2. **Q**: Should we provide a schema export for users to run in Supabase SQL Editor?
   **A**: Alembic migrations should work. Document `alembic upgrade head` workflow.

3. **Q**: Should we detect Supabase's `sslmode=require` automatically?
   **A**: Yes, Supabase provider should always set SSL mode.

## File Structure

```
src/storage/
├── providers/
│   ├── __init__.py       # Exports: DatabaseProvider, get_provider
│   ├── base.py           # DatabaseProvider protocol
│   ├── local.py          # LocalPostgresProvider
│   ├── supabase.py       # SupabaseProvider
│   └── factory.py        # get_provider() factory function
└── database.py           # Updated to use provider factory
```
