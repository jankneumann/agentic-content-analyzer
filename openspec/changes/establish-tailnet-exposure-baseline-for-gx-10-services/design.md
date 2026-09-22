# Design: Establish tailnet exposure baseline for gx-10 services

## Context

gx-10 runs the API, the worker, and OpenBao. Clients are the operator's
workstation (writes browser-session cookies to OpenBao), and phones/laptops (use
the API and web UI only). All are on one tailnet. No service may be reachable
from the LAN or the internet.

## Decisions

### D1. Loopback bind + `tailscale serve`, not a direct Tailscale-IP bind

Both services bind `127.0.0.1`; `tailscale serve` terminates TLS on the MagicDNS
name and proxies to loopback.

- Chrome requires a publicly trusted certificate for the API with no manual
  exception; serve obtains and renews a Let's Encrypt certificate for the
  MagicDNS name automatically. `tailscale cert` also works but leaves 90-day
  renewal and service restarts to the operator.
- A loopback bind does not depend on `tailscaled` being up before the service
  starts (a direct bind on `100.x.y.z` fails with "cannot assign requested
  address" at boot).
- Processes on gx-10 (worker, `aca backup run`) keep using `http://127.0.0.1:8200`
  and never depend on MagicDNS.

Direct bind remains a documented alternative (`ACA_BAO_BIND_ADDR` /
`ACA_API_HOST` set to the Tailscale IPv4).

### D2. Standalone gx-10 compose file, not an overlay

Compose merges `ports` across `-f` files by concatenation, so an overlay cannot
remove the dev overlay's `8200:8200` (`0.0.0.0`). The dev overlay is also a
`-dev` server. A standalone file under `deploy/gx10/` (mirroring
`deploy/backup/`) ships a real raft-backed server and leaves every dev default
untouched.

### D3. Raft storage

`aca backup run` captures OpenBao with `bao operator raft snapshot save`, so the
gx-10 server uses integrated storage (single node; `api_addr`/`cluster_addr` on
loopback; cluster port unpublished).

### D4. API runs under systemd via the existing entrypoint

gx-10 already assumes a venv at `/opt/aca/.venv` (`aca-backup.service`). The API
unit runs `docker-entrypoint.sh` (migrate, then uvicorn) through `/bin/bash` so
Railway, Docker, and gx-10 share one launch contract. The entrypoint therefore
gains `ACA_API_HOST` / `ACA_FORWARDED_ALLOW_IPS`, with defaults equal to today's
hard-coded values.

### D5. Forwarded-header trust narrowed on gx-10

uvicorn's resolved client IP keys the login rate limiter. Behind serve the only
legitimate proxy is loopback, so the unit sets `ACA_FORWARDED_ALLOW_IPS=127.0.0.1`.
No `x_forwarded_for_*` settings on OpenBao: with them, OpenBao rejects
connections from an authorized address that carry no `X-Forwarded-For`, which is
exactly what the local worker sends.

### D6. Workstation/mobile split by tag

Tailnet groups contain users, not devices. The workstation is `tag:workstation`
(API + 8200); phones and laptops stay user-owned devices of
`group:aca-operators` (API only). A `hosts` alias is documented for keeping the
workstation user-owned.

## Non-goals

- Changing `extension/manifest.json` (ri-15).
- Production-hardening Postgres/Neo4j/FalkorDB exposure on gx-10 (flagged in
  `docs/TAILNET.md` § Security notes).
- OpenBao init/unseal/AppRole procedure (docs/OPENBAO.md; ri-02 owns policies).
