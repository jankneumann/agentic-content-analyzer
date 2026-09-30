# Tasks: Establish tailnet exposure baseline for gx-10 services

> Change ID: `establish-tailnet-exposure-baseline-for-gx-10-services`

## 1. Tests first

- [x] 1.1 `tests/test_scripts/test_gx10_tailnet_exposure.py`: run `docker-entrypoint.sh` with recorder `alembic`/`uvicorn` on `PATH`; assert default argv unchanged and `ACA_API_HOST`/`PORT`/`ACA_FORWARDED_ALLOW_IPS` honoured; assert `*` is not glob-expanded
- [x] 1.2 Same file: gx-10 compose publishes only `${ACA_BAO_BIND_ADDR:-127.0.0.1}:8200:8200`, no dev mode, raft storage in `openbao.hcl`
- [x] 1.3 Same file: `aca-api.service` binds loopback, trusts only loopback proxy, reuses the entrypoint, unprivileged, no literal secret; env template defaults to loopback with placeholder credentials
- [x] 1.4 Same file: `docs/TAILNET.md` exists and is linked from `CLAUDE.md` and `docs/SETUP.md`; extension README names the tailnet URL and `host_permissions`

## 2. Implementation

- [x] 2.1 `docker-entrypoint.sh`: `--host "${ACA_API_HOST:-0.0.0.0}"`, `--port "${PORT:-8000}"`, `--forwarded-allow-ips="${ACA_FORWARDED_ALLOW_IPS:-*}"`
- [x] 2.2 `deploy/gx10/docker-compose.gx10.yml` (standalone OpenBao server, loopback publish) and `deploy/gx10/openbao.hcl` (raft, TLS terminated by serve)
- [x] 2.3 `deploy/gx10/aca-api.service` and `deploy/gx10/aca-gx10.env.example`
- [x] 2.4 Verify `docker compose -f deploy/gx10/docker-compose.gx10.yml config` renders host_ip `127.0.0.1` by default and the override address when `ACA_BAO_BIND_ADDR` is set; confirm the overlay-concatenation hazard

## 3. Documentation

- [x] 3.1 `docs/TAILNET.md`: topology, bind addresses, setup, `tailscale serve` recipe, HuJSON grants sketch with tests, client values (`BAO_ADDR`), CORS, listener check + expected output, alternatives, troubleshooting, security notes
- [x] 3.2 One-line links from `CLAUDE.md` Documentation Index and `docs/SETUP.md`
- [x] 3.3 `extension/README.md`: tailnet API URL and host-permission / `ALLOWED_ORIGINS` note (manifest unchanged; ri-15)

## 4. Validation

- [x] 4.1 `ruff check` / `ruff format` / `mypy` on the new test file
- [x] 4.2 Targeted pytest (`tests/test_scripts/`)
- [x] 4.3 `openspec validate establish-tailnet-exposure-baseline-for-gx-10-services --type change --strict`
- [ ] 4.4 Operator, on gx-10 (not possible in CI): run `docs/TAILNET.md` § Verify (listener check, negative LAN/phone checks, Chrome padlock on the MagicDNS URL)
