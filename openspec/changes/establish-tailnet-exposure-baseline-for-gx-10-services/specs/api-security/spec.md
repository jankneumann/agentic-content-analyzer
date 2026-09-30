## ADDED Requirements

### Requirement: Tailnet-only exposure of gx-10 services

The gx-10 deployment configuration SHALL bind the ACA API and OpenBao to a configurable host address that defaults to loopback (`127.0.0.1`), SHALL NOT publish either service on `0.0.0.0` or a LAN address, and SHALL NOT publish the OpenBao cluster port. Reachability from other machines SHALL be only through the Tailscale address of gx-10, gated by the tailnet policy.

#### Scenario: OpenBao is published on loopback by default
- **WHEN** `deploy/gx10/docker-compose.gx10.yml` is rendered with no `ACA_BAO_BIND_ADDR` set
- **THEN** the only published port is `8200`, with host IP `127.0.0.1`
- **AND** the OpenBao server runs without `-dev` and with raft storage

#### Scenario: Bind address is overridable without editing the file
- **WHEN** the compose file is rendered with `ACA_BAO_BIND_ADDR` set to the gx-10 Tailscale IPv4
- **THEN** port `8200` is published on that address only

#### Scenario: API unit binds loopback
- **WHEN** `deploy/gx10/aca-api.service` starts the API
- **THEN** uvicorn is launched with `--host 127.0.0.1` unless `/etc/aca/aca.env` overrides `ACA_API_HOST`
- **AND** the unit contains no `0.0.0.0` directive and no literal credential

#### Scenario: Listener check shows no wildcard listener
- **WHEN** the operator runs the listener check documented in `docs/TAILNET.md` on gx-10
- **THEN** no listener for port `8000` or `8200` has a local address of `0.0.0.0`, `*`, `[::]`, or a LAN address

### Requirement: Configurable API bind host and forwarded-header trust

The container entrypoint SHALL read the uvicorn bind host from `ACA_API_HOST`, the port from `PORT`, and the trusted proxy list for `X-Forwarded-*` headers from `ACA_FORWARDED_ALLOW_IPS`, with defaults `0.0.0.0`, `8000`, and `*` so existing container deployments are unchanged.

#### Scenario: Container defaults are preserved
- **WHEN** `docker-entrypoint.sh` runs with none of the variables set
- **THEN** uvicorn receives `--host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*`
- **AND** the `*` is passed literally, not glob-expanded

#### Scenario: gx-10 values are honoured
- **WHEN** `docker-entrypoint.sh` runs with `ACA_API_HOST=127.0.0.1`, `PORT=8123`, and `ACA_FORWARDED_ALLOW_IPS=127.0.0.1`
- **THEN** uvicorn receives `--host 127.0.0.1 --port 8123` and trusts forwarded headers only from `127.0.0.1`

### Requirement: Browser-trusted TLS on the MagicDNS name

The documented gx-10 recipe SHALL serve the API over HTTPS on `gx-10.<tailnet>.ts.net` with a publicly trusted certificate issued for that name (via `tailscale serve`, or `tailscale cert` as the documented alternative), and SHALL serve OpenBao to the workstation over HTTPS on port `8200` of the same name.

#### Scenario: Chrome opens the API without an exception
- **WHEN** an allowed tailnet device opens `https://gx-10.<tailnet>.ts.net/health` in Chrome after the documented `tailscale serve` steps
- **THEN** the page loads with a certificate issued by a public CA for that name and no interstitial or manually installed CA

#### Scenario: Workstation reaches OpenBao with certificate verification
- **WHEN** the workstation sets `BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`
- **THEN** OpenBao clients verify the certificate against the default trust store and connect

### Requirement: Tailnet exposure runbook

The repository SHALL include `docs/TAILNET.md`, linked from `CLAUDE.md` and `docs/SETUP.md`, recording the per-service bind addresses, a Tailscale policy sketch that grants phones and laptops the API only and the workstation the API plus port `8200`, the `tailscale serve` (or `tailscale cert`) recipe, the workstation `BAO_ADDR`, the CORS origins for browser clients on the MagicDNS name, the listener check with its expected output, and troubleshooting. The Chrome extension README SHALL state the tailnet API URL and the matching host-permission note.

#### Scenario: Operator follows the runbook from the documentation index
- **WHEN** an operator opens `CLAUDE.md` or `docs/SETUP.md`
- **THEN** each links to `docs/TAILNET.md`
- **AND** `docs/TAILNET.md` contains the `tag:gx10` policy sketch, `BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`, the `ss -ltnp` check, and the `ALLOWED_ORIGINS` guidance

#### Scenario: Extension user configures the tailnet API
- **WHEN** a user reads `extension/README.md`
- **THEN** it gives `https://gx-10.<tailnet>.ts.net` as the API URL and states the `host_permissions` entry that matches it, and that until the manifest declares it the extension origin must be in `ALLOWED_ORIGINS`
