# Neon Operations Runbook

Neon provides PostgreSQL with copy-on-write branching, scale-to-zero, and point-in-time recovery. It's the primary database for the `railway-neon` production profile.

## Architecture

```
Neon Project
  ├── main (branch)          — Production data, always-on endpoint
  ├── claude/feature-xyz     — Agent feature branch (ephemeral)
  ├── claude/test-migrations — Agent migration testing (ephemeral)
  └── staging                — Optional staging branch
```

Each branch gets its own read-write compute endpoint and connection string. Branches are copy-on-write from the parent — instant creation, minimal storage overhead.

## CLI Reference

The `aca neon` CLI wraps the Neon API. It reads `NEON_API_KEY` and `NEON_PROJECT_ID` from the active profile, `.secrets.yaml`, or environment.

```bash
# List branches
aca neon list

# Create branch (from main by default)
aca neon create claude/feature-xyz
aca neon create claude/feature-xyz --parent main
aca neon create claude/feature-xyz --force    # Delete existing + recreate

# Get connection string
aca neon connection claude/feature-xyz          # Pooled (PgBouncer)
aca neon connection claude/feature-xyz --direct  # Direct (for migrations)

# Delete branch
aca neon delete claude/feature-xyz
aca neon delete claude/feature-xyz --force      # Skip confirmation

# Clean stale branches (claude/* older than 24h)
aca neon clean --dry-run                        # Preview
aca neon clean --force                          # Execute

# Makefile shortcuts
make neon-list
make neon-create NAME=claude/feature-xyz
make neon-clean
```

## Configuration

Required settings (in `.secrets.yaml`, environment, or profile):

```yaml
# .secrets.yaml
NEON_API_KEY: neon_api_xxxxx
NEON_PROJECT_ID: your-project-id
NEON_DEFAULT_BRANCH: main
```

The `railway-neon` profile wires these automatically:

```yaml
# profiles/railway-neon.yaml
settings:
  database:
    neon_api_key: "${NEON_API_KEY:-}"
    neon_project_id: "${NEON_PROJECT_ID:-}"
    neon_default_branch: "${NEON_DEFAULT_BRANCH:-main}"
```

## Common Operations

### Create a feature branch

```bash
# Create branch
aca neon create claude/add-search

# Get connection string
export DATABASE_URL=$(aca neon connection claude/add-search)

# Run migrations against the branch
alembic upgrade head

# Work with the branch...

# Clean up when done
aca neon delete claude/add-search --force
```

### Test migrations safely

```bash
# Create throwaway branch
aca neon create claude/test-migration --force

# Try the migration
DATABASE_URL=$(aca neon connection claude/test-migration --direct) \
  alembic upgrade head

# If it works, apply to main
# If it fails, just delete the branch
aca neon delete claude/test-migration --force
```

### Clean up stale agent branches

```bash
# Preview what would be deleted
aca neon clean --dry-run

# Delete branches matching claude/* older than 24h
aca neon clean --force

# Custom prefix and age
aca neon clean --prefix "test/" --older-than 48 --force
```

### Check branch health

```bash
# Verify connectivity
CONN=$(aca neon connection claude/feature-xyz)
psql "$CONN" -c "SELECT 1"

# Check migration state
DATABASE_URL="$CONN" alembic current
```

## Troubleshooting

### First connection is slow (2-5s)

Neon scale-to-zero suspends idle compute endpoints. The first connection after inactivity triggers a cold start (2-5 seconds). This is normal behavior.

**Mitigation**: Increase connection timeout in application settings, or use always-on endpoints for production branches (paid feature).

### `NEON_API_KEY` or `NEON_PROJECT_ID` not set

```
Error: NEON_API_KEY and NEON_PROJECT_ID are required.
```

Ensure they're in one of:
1. Environment variables
2. `.secrets.yaml` (requires `PROFILE` to be set)
3. Active profile settings

Quick check:
```bash
echo "NEON_API_KEY: ${NEON_API_KEY:-(not set)}"
echo "NEON_PROJECT_ID: ${NEON_PROJECT_ID:-(not set)}"
```

### pgmq not available on Neon

Neon doesn't support pgmq (it requires C extensions). This is fine — the app uses PGQueuer which is pure SQL (`SELECT FOR UPDATE SKIP LOCKED`).

### Pooled vs Direct connections

- **Pooled** (default): Routes through PgBouncer. Use for application queries.
- **Direct**: Bypasses PgBouncer. Required for:
  - Alembic migrations
  - `LISTEN/NOTIFY` (used by the queue worker)
  - Advisory locks
  - Prepared statements

```bash
# Application queries
aca neon connection branch-name          # Pooled

# Migrations
aca neon connection branch-name --direct  # Direct
```

### Branch creation fails

If branch creation fails with a 409 Conflict, the branch already exists. Use `--force` to delete and recreate:

```bash
aca neon create claude/feature-xyz --force
```

### Cross-cloud latency

Railway and Neon are in different cloud providers. Expect 5-15ms per query overhead. Mitigate by matching AWS regions:
- Railway: Choose US-East-1 region
- Neon: Choose US-East-1 (AWS)

### Extensions available on Neon

Neon supports: `pgvector`, `pg_search` (ParadeDB), `pg_cron`, `pg_trgm`, `btree_gin`, `btree_gist`, and more.

Not available: `pgmq` (use PGQueuer instead).
