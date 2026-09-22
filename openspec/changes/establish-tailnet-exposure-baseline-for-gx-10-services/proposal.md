# Establish tailnet exposure baseline for gx-10 services

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-01`)
> Change ID: `establish-tailnet-exposure-baseline-for-gx-10-services`

## Why

The project is moving from Railway to the self-hosted gx-10 host, reached from
the operator's workstation, laptops, and phones over Tailscale. Every later item
in this roadmap (the `aca auth session` capture CLI writing cookies to OpenBao,
the worker healing rotated `ct0`, the extension syncing a session) assumes the
workstation and worker reach OpenBao and the API **privately** over the tailnet.

Nothing in the repository establishes that today:

- `docker-entrypoint.sh` hard-codes `uvicorn --host 0.0.0.0 --forwarded-allow-ips='*'`.
  Run on a host (rather than in a container whose published port decides
  exposure) that listens on every interface and lets any peer set
  `X-Forwarded-For`, which keys the login rate limiter.
- The only OpenBao compose file, `docker-compose.openbao.yml`, is a dev-mode
  server (in-memory, fixed root token) published on `0.0.0.0:8200`. A gx-10
  overlay cannot fix that: Compose concatenates `ports` across `-f` files, so the
  dev `8200:8200` survives any overlay (verified with `docker compose config`).
- There is no record of the bind addresses, the tailnet policy, how the API gets
  a certificate Chrome trusts, or which `BAO_ADDR` the workstation uses.
- The extension README does not say which URL to use for a tailnet API or that
  its requests are CORS-checked because the manifest has no host permission.

## What Changes

- **Configurable API bind.** `docker-entrypoint.sh` reads `ACA_API_HOST`
  (default `0.0.0.0`, unchanged for Railway/Docker) and `ACA_FORWARDED_ALLOW_IPS`
  (default `*`, unchanged) alongside the existing `PORT`.
- **`deploy/gx10/`** (new, mirrors `deploy/backup/`):
  - `docker-compose.gx10.yml` — standalone OpenBao server (raft storage, not dev
    mode) published on `${ACA_BAO_BIND_ADDR:-127.0.0.1}:8200`; 8201 unpublished.
  - `openbao.hcl` — raft storage (required by `aca backup run`'s
    `bao operator raft snapshot save`), plain-HTTP listener behind `tailscale serve`.
  - `aca-api.service` — systemd unit running the same entrypoint with
    `ACA_API_HOST=127.0.0.1` and `ACA_FORWARDED_ALLOW_IPS=127.0.0.1`.
  - `aca-gx10.env.example` — `/etc/aca/aca.env` template (placeholders only).
- **`docs/TAILNET.md`** — topology, bind-address table, `tailscale serve` recipe
  (API on 443, OpenBao on 8200, optional UI on 8443), HuJSON grants sketch with
  policy tests, workstation `BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`, CORS
  origins, `ss -ltnp` listener check with expected output and an assertion
  one-liner, alternatives (direct bind, `tailscale cert`), troubleshooting.
- Links from `CLAUDE.md` (Documentation Index) and `docs/SETUP.md`; tailnet API
  URL and host-permission note in `extension/README.md`. `extension/manifest.json`
  is **not** changed (ri-15 owns that).

## Impact

- Affected specs: `api-security` (ADDED requirements for tailnet-only exposure,
  configurable bind/forwarded trust, trusted TLS, and the runbook).
- Affected code: `docker-entrypoint.sh` only; no Python source changes. Defaults
  are unchanged, so Railway and local Docker behave exactly as before.
- New files: `deploy/gx10/*`, `docs/TAILNET.md`,
  `tests/test_scripts/test_gx10_tailnet_exposure.py`.
- Not verifiable in CI: live Tailscale behaviour (serve, certificates, policy).
  The shipped configuration is pinned by tests; the live checks are the
  operator-run steps in `docs/TAILNET.md` § Verify.
