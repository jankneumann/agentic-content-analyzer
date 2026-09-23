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
| `secret/newsletter/*` | Newsletter aggregator | `newsletter-read`; `newsletter-worker` and `newsletter-session-writer` add `patch` ([session roles](#session-credential-roles-workstation-and-worker)) |
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

### 5. Push a Single Secret From the CLI

`aca auth gmail|youtube --to bao` writes the freshly minted OAuth token into the
existing KV v2 secret (`BAO_MOUNT_PATH`/`BAO_SECRET_PATH`, default
`secret/newsletter`) with a server-side **PATCH** (`application/merge-patch+json`):

```bash
BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token aca auth gmail --to bao
```

- Only the named keys change, plus a sibling `<KEY>_SAVED_AT` (ISO-8601 UTC) per
  key. Every other key at the path (the LLM keys) is left byte-identical.
- The path must already exist: PATCH on a missing secret fails with a message
  pointing at the seed script above. The sink never creates the path, because
  that needs a full `create_or_update` write.
- The token needs only the `patch` capability on `secret/data/newsletter`, not
  `read`. That is why the sink does not use hvac's `kv.v2.patch()`, which is a
  client-side read followed by `create_or_update_secret`.
- Values are never printed; the CLI echoes key names and the target path only.

Implementation: `src/cli/secret_sinks.py` (`BaoSink`). Other sinks: `--to railway`
and `--to secrets-file` (`.secrets.yaml`, mode 0600).

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

### Session-Credential Roles (Workstation and Worker)

Browser-session cookies (`SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, `X_CT0`) and
OAuth tokens are written into the same KV v2 secret the app reads, with a
server-side **PATCH**. Two least-privilege roles cover the two writers:

```bash
# On gx-10, as the admin (implies --with-approle; safe to re-run)
BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$ADMIN_TOKEN \
  python scripts/bao_seed_newsletter.py --with-session-roles
```

| AppRole | Policies | Who uses it | Token TTL / max | Secret-id TTL |
|---------|----------|-------------|-----------------|---------------|
| `newsletter-workstation` | `newsletter-session-writer` | `aca auth ... --to bao` on the operator's workstation | 15 min / 1 h | 90 days |
| `newsletter-app` | `newsletter-read` + `newsletter-worker` | API and worker on gx-10 (rotated `ct0` write-back, API session endpoint) | `BAO_TOKEN_TTL` (1 h) / 24 h | unset |

Capabilities (default mount `secret`, path `newsletter`; both follow
`BAO_MOUNT_PATH` / `BAO_SECRET_PATH`):

| Policy | `secret/data/newsletter` | `secret/data/shared` | `secret/metadata/*`, `secret/delete/*`, `secret/destroy/*` |
|--------|--------------------------|----------------------|--------------------------------------------------------|
| `newsletter-read` | `read` | `read` | none |
| `newsletter-worker` | `read`, `patch` | none | none |
| `newsletter-session-writer` | `patch` | none | none |

No role gets `create`, `update`, `delete`, `destroy` or `list`, so none can
replace the whole secret, delete versions, or enumerate paths. What this rests on:

- **Why `patch` without `read` works.** The OpenBao sink (`BaoSink` in
  `src/cli/secret_sinks.py`) sends an HTTP `PATCH` with
  `Content-Type: application/merge-patch+json`, which the server merges and which
  needs only the `patch` capability. hvac's `kv.v2.patch()` must **not** be used
  with these roles: in hvac 2.4 it is `read_secret_version()` followed by
  `create_or_update_secret(cas=...)`, which needs `read` plus `update` and would
  fail with 403 for the workstation.
- **PATCH is path-scoped, not key-scoped.** KV v2 ACLs cannot restrict which keys
  inside the secret a PATCH touches (`allowed_parameters` only sees the top-level
  `data` object). A leaked workstation credential could therefore overwrite or
  null out other keys, but could never read them. The short token TTL and the
  90-day secret-id TTL bound that window.
- **The secret must already exist.** PATCH on a missing path returns 404. Run the
  plain seed (`python scripts/bao_seed_newsletter.py`) once first.
- **Re-runs are idempotent.** Each policy is compared with what is stored and
  reported as `created`, `updated` or `unchanged`. A later plain `--with-approle`
  run keeps `newsletter-worker` on `newsletter-app` rather than silently revoking
  the worker's write-back.
- **Expect one warning on the workstation.** If `BAO_ADDR` is exported when the
  CLI loads its settings, the startup read of `secret/data/newsletter` is denied
  and logged as `bao.connection_error`. That is by design and does no harm: settings
  fall back to env and profile values, and the sink's PATCH still succeeds.

#### Getting the workstation its secret-id over the tailnet

The workstation reaches OpenBao only over Tailscale, at
`BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`. The bind addresses, `tailscale serve`
setup and ACL are in [TAILNET.md](TAILNET.md#client-values). Never paste a bare
secret-id into chat or a ticket. Hand it over response-wrapped:

```bash
# 1. On gx-10 (admin token): mint a single-use wrapping token that expires in 5 min.
#    The role_id is printed by the seed script and is not secret.
bao write -wrap-ttl=5m -f auth/approle/role/newsletter-workstation/secret-id

# 2. On the workstation: unwrap it over the tailnet (the wrapping token is its own auth)
export BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200
bao unwrap -field=secret_id <wrapping-token>

# 3. Keep role_id + secret_id in the workstation's shell/profile secrets
export BAO_ROLE_ID=<newsletter-workstation role_id>
export BAO_SECRET_ID=<unwrapped secret_id>
aca auth gmail --to bao
```

If `bao unwrap` reports that the wrapping token was already used, assume someone
intercepted it. List the role's secret-id accessors with
`bao list auth/approle/role/newsletter-workstation/secret-id`, destroy the
unexpected one with
`bao write auth/approle/role/newsletter-workstation/secret-id-accessor/destroy secret_id_accessor=<accessor>`,
and mint a new one. Do not add `token_bound_cidrs` for the tailnet range (`100.64.0.0/10`).
`tailscale serve` proxies from loopback, so OpenBao sees every workstation
request as coming from `127.0.0.1`.

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
