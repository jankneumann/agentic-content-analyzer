# OpenBao Secrets Management

Central [OpenBao](https://openbao.org/) (open-source Vault fork) integration for secrets management. Secrets are fetched from KV v2 and injected into the Pydantic Settings resolution chain.

## Architecture

```
                    Resolution Order
                    ================
              1. Environment variables (always win)
              2. OpenBao KV v2 (this module)
              3. Profile values (profiles/*.yaml)
              4. .env file
              5. Pydantic defaults
```

### Central Deployment

A single OpenBao instance serves multiple projects with namespaced paths:

| Path | Project | Access |
|------|---------|--------|
| `secret/newsletter/*` | Newsletter aggregator | `newsletter-read` policy |
| `secret/coordinator/*` | Agent coordinator | `coordinator-read` policy |
| `secret/shared/*` | Cross-project keys | Both policies |

### Key Files

| File | Purpose |
|------|---------|
| `src/config/bao_secrets.py` | Core module: client auth, caching, `BaoSettingsSource`, token refresh |
| `src/config/secrets.py` | `resolve_secret()` with OpenBao tier |
| `src/config/settings.py` | Wires `BaoSettingsSource` into Pydantic sources |
| `scripts/bao_seed_newsletter.py` | Seeding script for dev/CI setup |
| `docker-compose.openbao.yml` | Dev server overlay |
| `profiles/local-openbao.yaml` | Dev profile for OpenBao workflow |

## Quick Start (Local Development)

### 1. Start OpenBao

```bash
docker compose -f docker-compose.yml -f docker-compose.openbao.yml up -d
```

This starts OpenBao in **dev mode** (unsealed, in-memory) with root token `dev-root-token`.

### 2. Seed Secrets

```bash
# Preview what will be written
BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \
  python scripts/bao_seed_newsletter.py --dry-run

# Seed from .secrets.yaml
BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \
  python scripts/bao_seed_newsletter.py
```

### 3. Run with OpenBao

```bash
export PROFILE=local-openbao
export BAO_ADDR=http://localhost:8200
export BAO_TOKEN=dev-root-token
python -m src.api.app
```

The application resolves secrets from OpenBao automatically. If OpenBao is unavailable, it falls through to `.secrets.yaml` and `.env` -- no code changes needed.

### 4. Install the Client Library

```bash
pip install '.[vault]'
```

The `hvac` library is an optional dependency. Without it, OpenBao integration is silently skipped.

## Production Deployment

### AppRole Authentication

For production, use AppRole instead of root tokens:

```bash
# Create AppRole during setup
BAO_ADDR=https://bao.example.com BAO_TOKEN=$ADMIN_TOKEN \
  python scripts/bao_seed_newsletter.py --with-approle

# Application uses role_id + secret_id
export BAO_ADDR=https://bao.example.com
export BAO_ROLE_ID=<role-id>
export BAO_SECRET_ID=<secret-id>
```

The `_BaoTokenManager` automatically refreshes tokens at 75% of their TTL using a background `threading.Timer`. On refresh, secrets are reloaded atomically (dict reference swap).

### Dynamic Database Credentials

```bash
BAO_ADDR=https://bao.example.com BAO_TOKEN=$ADMIN_TOKEN \
  POSTGRES_DSN=postgresql://admin:password@db:5432/newsletters \
  python scripts/bao_seed_newsletter.py --with-db-engine
```

Creates a `newsletter-app` database role with:
- Default TTL: 1 hour
- Max TTL: 24 hours
- Grants: SELECT, INSERT, UPDATE, DELETE on public schema

### Shared Keys

Write selected keys to `secret/shared/` for cross-project access:

```bash
python scripts/bao_seed_newsletter.py \
  --shared-keys ANTHROPIC_API_KEY,OPENAI_API_KEY
```

Merge semantics: newsletter values win on conflict, other projects' keys are preserved.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAO_ADDR` | Yes* | -- | OpenBao server URL |
| `BAO_TOKEN` | Dev only | -- | Root/admin token (dev mode) |
| `BAO_ROLE_ID` | Prod | -- | AppRole role ID |
| `BAO_SECRET_ID` | Prod | -- | AppRole secret ID |
| `BAO_MOUNT_PATH` | No | `secret` | KV v2 mount path |
| `BAO_SECRET_PATH` | No | `newsletter` | Path under the mount |

*Without `BAO_ADDR`, OpenBao is completely bypassed (graceful degradation).

## Thread Safety

All secret access is protected by a module-level `threading.Lock` with double-check locking:

1. Fast path: check `_bao_checked` flag (no lock)
2. Slow path: acquire lock, re-check, fetch, cache atomically via reference swap

The `BaoSettingsSource` wraps all operations in try/except to ensure `Settings()` instantiation never fails due to vault issues.

## Audit Events

All operations emit structured log messages for observability:

| Event | Level | When |
|-------|-------|------|
| `bao.secrets_loaded` | INFO | Secrets successfully loaded from vault |
| `bao.token_refreshed` | INFO | Token refresh + secret reload succeeded |
| `bao.auth_success` | INFO | AppRole or token authentication succeeded |
| `bao.auth_failure` | WARNING | Authentication failed (bad token, missing creds) |
| `bao.connection_error` | WARNING | Network error, timeout, or hvac not installed |
| `bao.token_manager_stopped` | DEBUG | Background refresh timer cancelled |

## Testing

```bash
# Unit tests (no OpenBao required)
pytest tests/test_config/test_bao_secrets.py -v

# Integration tests (resolve_secret chain)
pytest tests/test_config/test_bao_settings_integration.py -v

# Seeding script tests
pytest tests/test_config/test_bao_seeding.py -v
```

All tests mock the `hvac` library -- no running OpenBao instance needed.
