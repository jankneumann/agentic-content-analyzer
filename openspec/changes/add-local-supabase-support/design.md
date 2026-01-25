## Context

Supabase provides a complete local development stack via Docker or the Supabase CLI.
This enables full dev/prod parity without requiring cloud connectivity.

## Goals

- Enable offline Supabase development
- Provide dev/prod parity for testing
- Support schema synchronization between local and cloud
- Reduce cloud costs during development
- Enable CI/CD testing without cloud dependency

## Non-Goals

- Replace existing local PostgreSQL option (keep as simpler alternative)
- Migrate existing local data to Supabase
- Require Supabase for all development

## Local Supabase Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  PostgreSQL  │  │   Storage    │  │    Studio    │       │
│  │  :54322      │  │   :54321     │  │   :54323     │       │
│  │              │  │  (S3 API)    │  │  (Admin UI)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                                  │
│         └────────┬────────┘                                  │
│                  │                                           │
│         ┌────────▼────────┐                                  │
│         │   Application   │                                  │
│         │   (FastAPI)     │                                  │
│         └─────────────────┘                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Supabase CLI vs Docker Compose

**Choice**: Support both approaches

| Approach | Pros | Cons |
|----------|------|------|
| Supabase CLI | Official, full features, schema sync | Requires CLI install |
| Docker Compose | Integrated with existing stack | Less features |

**Recommendation**:
- Use Supabase CLI for full development (schema sync, migrations)
- Provide Docker Compose option for CI/CD and simple testing

### Decision 2: Settings Auto-Detection

**Choice**: Explicit `SUPABASE_LOCAL=true` flag

```python
# .env for local development
SUPABASE_LOCAL=true
# All other Supabase settings auto-configured

# .env for cloud (explicit)
SUPABASE_LOCAL=false
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_PROJECT_REF=xxx
```

**Rationale**: Explicit is better than magic. Prevents accidental cloud/local mixing.

### Decision 3: Default Ports

**Choice**: Use Supabase CLI defaults

| Service | Port |
|---------|------|
| API (PostgREST, Storage, Auth) | 54321 |
| Database (PostgreSQL) | 54322 |
| Studio (Admin UI) | 54323 |
| Inbucket (Email testing) | 54324 |

**Rationale**: Matches official Supabase CLI, reduces confusion.

### Decision 4: Schema Sync Workflow

**Choice**: Supabase CLI migrations (not Alembic)

For Supabase-specific features (RLS, Storage policies), use Supabase migrations:
```bash
supabase db diff -f my_migration   # Generate from changes
supabase db push                    # Push to cloud
supabase db pull                    # Pull from cloud
```

For application models, continue using Alembic (works with any PostgreSQL).

**Rationale**: Supabase migrations capture Supabase-specific features that Alembic cannot.

## Environment Switching

```bash
# Local development
export SUPABASE_LOCAL=true
supabase start
python -m src.main

# Cloud deployment
export SUPABASE_LOCAL=false
export SUPABASE_URL=https://xxx.supabase.co
python -m src.main
```

## Risks / Trade-offs

- **Risk**: Confusion between local and cloud data
  - Mitigation: Clear logging of which environment is active

- **Risk**: Schema drift between local and cloud
  - Mitigation: Document schema sync workflow, add CI checks

- **Risk**: Local Supabase resource usage
  - Mitigation: Document memory requirements (~2GB), add `supabase stop` guidance

## Local Supabase Requirements

- Docker Desktop or Docker Engine
- ~2GB RAM for full stack
- Supabase CLI (optional but recommended)
- Ports 54321-54324 available
