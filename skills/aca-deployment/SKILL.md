---
name: aca-deployment
description: Production deployment management for Railway + Neon + AuraDB stack
category: Deployment
tags: [deployment, railway, neon, auradb, production, infrastructure]
triggers:
  - "deploy"
  - "deployment status"
  - "check production"
  - "neon branch"
  - "railway deploy"
  - "auradb status"
  - "stack health"
---

# ACA Deployment Skill

Manage the production deployment stack: Railway (compute + storage), Neon (PostgreSQL with branching), and Neo4j AuraDB (knowledge graph). This skill wraps existing CLIs (`aca`, `railway`, `neonctl`, `aura`) and integrates with the profile system.

## Relationship to Vendor Skills

This skill and the vendor-provided skills are **complementary**:

| Use this skill (`aca-deployment`) for | Use `use-railway` for | Use `neon-postgres` for |
|---|---|---|
| Multi-provider stack orchestration | Railway project/service creation | Neon platform docs and best practices |
| Neon branch lifecycle (create/cleanup) | Build/deploy troubleshooting | Connection methods and drivers |
| AuraDB instance management | Domain and networking config | Branching strategies and workflows |
| Cross-provider health checks (`stack:verify`) | Environment/variable management | Autoscaling, scale-to-zero tuning |
| Profile-aware deployments | Railway metrics and monitoring | Neon CLI and API reference |
| ACA-specific deploy pipeline | Railway database provisioning | Read replicas, connection pooling |
| | Railway GraphQL API queries | Neon Auth and SDK integration |

A third skill, `claimable-postgres`, provisions instant throwaway Neon databases via `pg.new` — useful for prototyping and ephemeral test environments.

**Rule of thumb**:
- `aca-deployment` → Stack-level operations (deploy all, verify providers, manage Neon branches/AuraDB)
- `use-railway` → Railway-specific operations (build config, domains, troubleshooting, metrics)
- `neon-postgres` → Neon platform knowledge (connection methods, branching strategies, SDK/API docs)
- `claimable-postgres` → Quick throwaway databases for prototyping (no account needed, 72h expiry)

## Arguments

`$ARGUMENTS` - Action name (required), optionally followed by action-specific arguments.

Format: `<provider>:<action> [args...]`

Examples:
- `stack:verify` — Full-stack health check
- `neon:create claude/feature-xyz` — Create Neon branch
- `railway:logs backend` — Tail Railway backend logs
- `auradb:status` — Check AuraDB instance status

## Prerequisites

Run the prerequisites check first:

```bash
SKILL_DIR="$(git rev-parse --show-toplevel)/skills/aca-deployment"
bash "$SKILL_DIR/scripts/check-prerequisites.sh"
```

| CLI | Install | Auth Check |
|-----|---------|------------|
| `aca` | Built-in (`python -m src.cli`) | `aca --help` |
| `railway` | `npm i -g @railway/cli` | `railway whoami` |
| `neonctl` | `npm i -g neonctl` | `neonctl me` |
| `aura` | [GitHub releases](https://github.com/neo4j/aura-cli/releases) | `aura version` |

Each provider section degrades gracefully when its CLI is missing — actions print a clear "CLI not installed" message and skip.

## Profile Integration

Actions are profile-aware. The active profile determines which providers are configured:

```bash
# Check active profile
aca profile show ${PROFILE:-local}

# The railway-neon profile defines the full production stack:
#   database: neon, neo4j: auradb, storage: railway, observability: braintrust
```

Key profiles:
- `railway-neon` — Production: Railway compute + Neon DB + AuraDB
- `railway` — Alternative: Railway compute + Railway DB + AuraDB
- `local` — Development: Docker Compose everything

---

## Actions

### Railway Actions

Railway hosts the API backend, frontend, and MinIO storage as separate services.

#### `railway:status`

Show Railway service status and recent deployments.

```bash
# Check Railway CLI
if ! command -v railway &>/dev/null; then
  echo "SKIP: railway CLI not installed. Install: npm i -g @railway/cli"
  exit 0
fi

# Verify authentication
if ! railway whoami 2>/dev/null; then
  echo "ERROR: Not logged in. Run: railway login"
  exit 1
fi

# Show project status
railway status

# List recent deployments
railway deployments list --limit 5
```

#### `railway:deploy`

Trigger a deployment from the current branch or latest commit.

```bash
if ! command -v railway &>/dev/null; then
  echo "SKIP: railway CLI not installed"
  exit 0
fi

# Parse optional service name from arguments
SERVICE="${1:-}"

if [ -n "$SERVICE" ]; then
  echo "Deploying service: $SERVICE"
  railway up --service "$SERVICE" --detach
else
  echo "Deploying all services..."
  railway up --detach
fi

echo ""
echo "Deployment triggered. Monitor with: railway logs"
```

#### `railway:logs`

Tail logs for a Railway service.

```bash
if ! command -v railway &>/dev/null; then
  echo "SKIP: railway CLI not installed"
  exit 0
fi

# Parse service name: backend, frontend, worker, or minio
SERVICE="${1:-backend}"

echo "Tailing logs for: $SERVICE"
echo "  (Ctrl+C to stop)"
echo ""

railway logs --service "$SERVICE"
```

#### `railway:env`

List or set Railway environment variables.

```bash
if ! command -v railway &>/dev/null; then
  echo "SKIP: railway CLI not installed"
  exit 0
fi

# Parse subcommand: list (default) or set KEY=VALUE
SUBCMD="${1:-list}"

if [ "$SUBCMD" = "list" ]; then
  railway variables list
elif [ "$SUBCMD" = "set" ]; then
  shift
  for VAR in "$@"; do
    KEY="${VAR%%=*}"
    VALUE="${VAR#*=}"
    echo "Setting $KEY..."
    railway variables set "$KEY=$VALUE"
  done
  echo "Variables updated. Redeploy to apply."
else
  echo "Usage: railway:env [list|set KEY=VALUE ...]"
fi
```

#### `railway:restart`

Restart a Railway service.

```bash
if ! command -v railway &>/dev/null; then
  echo "SKIP: railway CLI not installed"
  exit 0
fi

SERVICE="${1:-backend}"

echo "Restarting service: $SERVICE"
railway service restart --service "$SERVICE"
echo "Service restarted. Check status with: railway status"
```

---

### Neon Actions

Neon provides PostgreSQL with copy-on-write branching. These actions wrap the existing `aca neon` CLI subcommands.

#### `neon:list`

List all Neon database branches.

```bash
# Uses built-in aca CLI (always available)
aca neon list
```

Requires `NEON_API_KEY` and `NEON_PROJECT_ID` in environment, `.secrets.yaml`, or active profile.

#### `neon:create`

Create a new database branch for agent workflows or feature development.

```bash
# Parse branch name from arguments
BRANCH_NAME="${1:?Branch name required (e.g., claude/feature-xyz)}"
PARENT="${2:-main}"

echo "Creating Neon branch: $BRANCH_NAME (parent: $PARENT)"
aca neon create "$BRANCH_NAME" --parent "$PARENT"

echo ""
echo "To use this branch:"
echo "  export DATABASE_URL=\$(aca neon connection $BRANCH_NAME)"
echo "  alembic upgrade head  # Run migrations against the branch"
```

Use `--force` to recreate an existing branch:
```bash
aca neon create "$BRANCH_NAME" --parent "$PARENT" --force
```

#### `neon:verify`

Verify branch connectivity and optionally run migrations.

```bash
BRANCH_NAME="${1:?Branch name required}"

echo "Verifying Neon branch: $BRANCH_NAME"

# Get connection string
CONN_STR=$(aca neon connection "$BRANCH_NAME" 2>/dev/null)
if [ -z "$CONN_STR" ]; then
  echo "ERROR: Could not get connection string for branch: $BRANCH_NAME"
  exit 1
fi
echo "  Connection: OK"

# Test connectivity with psql (if available)
if command -v psql &>/dev/null; then
  if psql "$CONN_STR" -c "SELECT 1" >/dev/null 2>&1; then
    echo "  Connectivity: OK"
  else
    echo "  Connectivity: FAILED (Neon may be waking from scale-to-zero, retry in 5s)"
  fi
else
  echo "  Connectivity: SKIPPED (psql not installed)"
fi

# Optionally run migrations
if [ "${2:-}" = "--migrate" ]; then
  echo "  Running migrations..."
  DATABASE_URL="$CONN_STR" alembic upgrade head
  echo "  Migrations: OK"
fi
```

**Note**: Neon scale-to-zero instances take 2-5s to wake up on first connection. Retry if the first attempt fails.

#### `neon:cleanup`

Delete a specific Neon branch.

```bash
BRANCH_NAME="${1:?Branch name required}"

echo "Deleting Neon branch: $BRANCH_NAME"
aca neon delete "$BRANCH_NAME" --force
```

#### `neon:clean`

Clean up stale agent branches (older than 24h with `claude/` prefix by default).

```bash
# Parse optional flags
DRY_RUN="${1:-}"

if [ "$DRY_RUN" = "--dry-run" ]; then
  aca neon clean --dry-run
else
  aca neon clean --force
fi
```

---

### AuraDB Actions

Neo4j AuraDB hosts the knowledge graph. The `aura` CLI manages instances.

#### `auradb:status`

Show AuraDB instance status and details.

```bash
if ! command -v aura &>/dev/null; then
  echo "SKIP: aura CLI not installed."
  echo "  Install from: https://github.com/neo4j/aura-cli/releases"
  echo ""
  echo "Fallback: Check AuraDB status via Neo4j profile settings:"
  aca profile show ${PROFILE:-local} 2>/dev/null | grep -i neo4j || echo "  No Neo4j configuration in active profile"
  exit 0
fi

# List instances and their status (running/paused/creating)
aura instance list --output table
```

AuraDB instance states: `running`, `paused`, `creating`, `destroying`, `restoring`.

#### `auradb:pause`

Pause an AuraDB instance for cost savings during off-hours.

```bash
if ! command -v aura &>/dev/null; then
  echo "SKIP: aura CLI not installed"
  exit 0
fi

INSTANCE_ID="${1:?Instance ID required. Run 'auradb:status' to find it.}"

echo "Pausing AuraDB instance: $INSTANCE_ID"
aura instance pause "$INSTANCE_ID"
echo ""
echo "Instance pausing. Knowledge graph queries will return errors until resumed."
echo "Resume with: auradb:resume $INSTANCE_ID"
```

**Warning**: While paused, all Neo4j queries will fail. The application's `/ready` endpoint does not check Neo4j, so it will still report healthy.

#### `auradb:resume`

Resume a paused AuraDB instance.

```bash
if ! command -v aura &>/dev/null; then
  echo "SKIP: aura CLI not installed"
  exit 0
fi

INSTANCE_ID="${1:?Instance ID required}"

echo "Resuming AuraDB instance: $INSTANCE_ID"
aura instance resume "$INSTANCE_ID"
echo ""
echo "Instance resuming. May take 1-2 minutes to become fully available."
echo "Check status with: auradb:status"
```

#### `auradb:snapshot`

Create a backup snapshot of the AuraDB instance.

```bash
if ! command -v aura &>/dev/null; then
  echo "SKIP: aura CLI not installed"
  exit 0
fi

INSTANCE_ID="${1:?Instance ID required}"

echo "Creating snapshot of AuraDB instance: $INSTANCE_ID"
aura instance snapshot create "$INSTANCE_ID"
echo "Snapshot creation initiated."
```

---

### Cross-Cutting Actions

#### `stack:verify`

Full-stack health check across all configured providers. Uses the verify-deployment script.

```bash
SKILL_DIR="$(git rev-parse --show-toplevel)/skills/aca-deployment"
bash "$SKILL_DIR/scripts/verify-deployment.sh"
```

This checks:
1. **Railway**: API health (`/health`) and readiness (`/ready`) endpoints
2. **Neon**: Branch list connectivity via `aca neon list`
3. **AuraDB**: Instance status via `aura` CLI (or profile config fallback)
4. **Profile**: Active profile and provider configuration

#### `stack:profile`

Show the active profile and resolved provider configuration.

```bash
echo "=== Active Profile ==="
echo "PROFILE=${PROFILE:-<not set, using .env fallback>}"
echo ""

if [ -n "${PROFILE:-}" ]; then
  aca profile show "$PROFILE"
  echo ""
  echo "=== Provider Validation ==="
  aca profile validate "$PROFILE"
else
  echo "No profile active. Showing environment-based configuration:"
  echo "  DATABASE_PROVIDER=${DATABASE_PROVIDER:-local}"
  echo "  NEO4J_PROVIDER=${NEO4J_PROVIDER:-local}"
  echo "  STORAGE_PROVIDER=${STORAGE_PROVIDER:-local}"
  echo "  OBSERVABILITY_PROVIDER=${OBSERVABILITY_PROVIDER:-noop}"
  echo ""
  echo "Tip: Set PROFILE=railway-neon for production stack management"
fi
```

---

## OpenSpec Integration

This skill integrates with the OpenSpec development lifecycle:

| Phase | Skill | Deployment Action |
|-------|-------|-------------------|
| Before implementation | `/openspec-apply-change` | `neon:create claude/<change-name>` |
| During verification | `/validate-feature` | `stack:verify` (against Neon branch) |
| After archiving | `/openspec-archive-change` | `neon:cleanup claude/<change-name>` |

These are optional manual invocations. The OpenSpec skills don't automatically call deployment actions.

**Example workflow:**
```bash
# 1. Create isolated DB branch before implementing
/aca-deployment neon:create claude/add-search-feature

# 2. Work with the branch
export DATABASE_URL=$(aca neon connection claude/add-search-feature)
alembic upgrade head

# 3. Validate the full stack
/aca-deployment stack:verify

# 4. Clean up after merging
/aca-deployment neon:cleanup claude/add-search-feature
```

---

## Troubleshooting

For provider-specific troubleshooting, see the runbooks:
- [Railway Runbook](docs/railway-runbook.md)
- [Neon Runbook](docs/neon-runbook.md)
- [AuraDB Runbook](docs/auradb-runbook.md)

### Common Issues

| Issue | Solution |
|-------|----------|
| `NEON_API_KEY` not set | Add to `.secrets.yaml` or environment; ensure profile references it |
| Railway CLI not authenticated | Run `railway login` and link project with `railway link` |
| Neon branch takes 5s to connect | Scale-to-zero cold start; retry after initial connection |
| AuraDB instance paused | Run `auradb:resume <id>` and wait 1-2 minutes |
| Profile not loading | Ensure `PROFILE` env var is set; validate with `aca profile validate` |
| Cross-cloud latency (Railway <-> Neon) | Match AWS regions between providers |
