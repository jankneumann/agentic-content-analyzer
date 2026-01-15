# Design: Supabase Cloud Database Support

## Context

The newsletter aggregator currently requires local PostgreSQL via Docker Compose. This creates friction for new users and limits deployment flexibility. We want to support Supabase as a cloud alternative while maintaining backward compatibility.

**Reference Implementation**: [kbroose/stash](https://github.com/kbroose/stash) - A self-hosted app where users bring their own Supabase instance.

## Goals

1. Support Supabase as a first-class database option
2. Abstract database provider selection from application code
3. Maintain 100% backward compatibility with local PostgreSQL
4. Handle Supabase-specific features (connection pooling, SSL)

## Non-Goals

1. Storage provider (separate proposal)
2. Content sharing (separate proposal)
3. Chrome extension (separate proposal)
4. Multi-tenancy within a single Supabase instance

## Decisions

### Decision 1: Provider Abstraction Pattern

**What**: Create a `DatabaseProvider` protocol with implementations for each provider.

**Why**: Allows provider-specific configuration without polluting the core database module. Follows the same pattern as `DocumentParser` in the parsers module.

```python
# src/storage/providers/base.py
class DatabaseProvider(Protocol):
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
# Transaction pooling (recommended, port 6543)
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Session pooling (for prepared statements, port 5432)
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# Direct connection (no pooling, limited connections)
postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
```

**SQLAlchemy Configuration for Transaction Mode**:
```python
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

**Why**: Individual settings are easier for users unfamiliar with PostgreSQL connection strings.

```python
def get_database_url(self) -> str:
    if self.supabase_project_ref and self.supabase_db_password:
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
- Direct connection URL needed for migrations (bypasses pooler)
- Users can set `SUPABASE_DIRECT_URL` for DDL operations

## Alternatives Considered

### Alternative A: Environment Variable Only (No Abstraction)
Just detect `.supabase.` in DATABASE_URL and apply different engine options.

**Rejected**: Harder to add future providers, configuration logic scattered.

### Alternative B: Supabase Python SDK
Use `supabase-py` library for database access.

**Rejected**: Loses SQLAlchemy ORM features, would require rewriting all database code.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Supabase free tier limits (500MB, 50 connections) | Document limits, recommend upgrade for production |
| Transaction mode pooling gotchas | Default to transaction mode with proper config |
| Migration through pooler fails | Document direct URL requirement for migrations |

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
