# GX-10 production setup with Podman

This is the operator runbook for running Agentic Content Analyzer on the GX-10
with **Podman**, not Docker. It covers the `PROFILE=gx10` local-production
stack: PostgreSQL, Redis, Neo4j, OpenBao, Langfuse, ClickHouse, MinIO, Caddy,
Squid, the API, workers, schedulers, and maintenance services.

> **Status:** This is the Podman target runbook. The checked-in GX-10 Compose
> file, validation scripts, and some systemd units still invoke `docker` or
> `docker compose`. Complete the explicit conversion in [Step 5](#5-convert-the-runtime-to-podman)
> and retain its evidence before declaring the stack Podman-ready.

The GX-10 stack is passive until a separately approved cutover. Do not redirect
Railway traffic, public DNS, or shared-environment authority as part of this
runbook.

## 1. Operating model

Use **rootful Podman under systemd**. Rootless Podman is appropriate for local
development, but not for this production host: the stack needs root-owned
`0600` secrets, firewall changes, host ports, systemd credentials, and durable
paths under `/srv` and `/var/lib`.

Podman is daemonless. Do not depend on `docker.service`, and do not invent a
`podman.service` dependency. Order ACA units after `network-online.target` and
have systemd execute rootful Podman commands directly.

| Required before installation | Reason |
| --- | --- |
| Root or passwordless `sudo` | Runtime, firewall, credentials, and data paths are root-managed. |
| ARM64 immutable image digests | GX-10 is ARM64; mutable tags can change the executed image. |
| Approved published Squid image | `ubuntu/squid:6.13-25.10_beta` returned 404 during validation. A digest cannot repair a missing source tag/provenance policy. |
| OpenBao recovery material and first-install seed | Initialization and unseal are operator ceremonies, never normal startup. |
| External-provider credentials | Model, video, mail, and delivery APIs stay external by design. |
| `age` recipient and escrowed decrypt identities | Loss of all identities makes encrypted backups unrecoverable. |
| Maintenance window | Needed for cold-restart, dependency-loss, and native restore evidence. |

Never put secrets in Git, Compose files, shell history, unit command lines, or
chat transcripts.

## 2. Host layout

| Path | Mode | Purpose |
| --- | --- | --- |
| `/opt/aca` | `root:root`, not writable by group/other | Reviewed code and deployment assets. |
| `/etc/aca/gx10` | `0700` root-owned | Image policy, OpenBao operator material, first-install seed, maintenance plans. |
| `/run/aca/gx10` | `0700` root-owned | Short-lived, rendered per-role `0600` secrets. |
| `/srv/aca` | `0700` root-owned | Persistent application and service volumes. |
| `/var/lib/aca/gx10` | `0700` systemd state | Controller, backup, and restore evidence. |
| `/srv/aca/validation` | `0700` root-owned | Checksum-protected clean-stack evidence. |

Create the required paths. Do not delete a volume to reset a failed deployment.

```bash
sudo useradd --system --home /var/lib/aca --shell /usr/sbin/nologin aca 2>/dev/null || true
sudo install -d -o root -g root -m 0755 /opt/aca
sudo install -d -o root -g root -m 0700 /etc/aca/gx10 /run/aca/gx10 /srv/aca /srv/aca/validation /var/lib/aca/gx10
sudo install -d -o root -g root -m 0700 \
  /srv/aca/application /srv/aca/postgres /srv/aca/langfuse-postgres /srv/aca/redis \
  /srv/aca/neo4j /srv/aca/neo4j-logs /srv/aca/clickhouse /srv/aca/clickhouse-logs \
  /srv/aca/minio /srv/aca/openbao /srv/aca/caddy-data /srv/aca/caddy-config /srv/aca/squid-logs
```

Container images select their own users. If a bind mount fails permission checks,
inspect that image's user and initialization contract; do not recursively chmod
or chown `/srv/aca` to a guessed UID.

## 3. Install and verify host prerequisites

On Ubuntu, install the verified ARM64 packages appropriate for the release:

```bash
sudo apt update
sudo apt install -y podman podman-compose skopeo fuse-overlayfs \
  jq curl ca-certificates openssl age tar coreutils
# Ubuntu 24.04 (Noble) supplies PostgreSQL 16 by default. Add stable PGDG
# packages because the PostgreSQL 17 server needs a matching-major dump client.
. /etc/os-release
sudo install -d -m 0755 /usr/share/postgresql-common/pgdg
sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
printf 'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt %s-pgdg main\n' \
  "$VERSION_CODENAME" | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
sudo apt update
sudo apt install -y postgresql-client-17

sudo podman info --format '{{.Host.Security.Rootless}}'  # must print false
sudo podman-compose --version
skopeo --version
age --version
pg_dump --version
pg_restore --version
```

Also install and version-record these native tools when their components are
enabled: `neo4j-admin`, `clickhouse-backup`, MinIO `mc`, and the OpenBao `bao`
client. Use verified ARM64 releases; do not use an unreviewed `curl | sh`
installer.

The rootful context is the only one that matters for the system units:

```bash
sudo podman info
sudo podman network ls
sudo ss -ltnp
```

Do not grant a normal application account access to the rootful Podman socket.

## 4. Deploy a reviewed release and image policy

Deploy a reviewed commit, release tag, or artifact to `/opt/aca`; record its SHA
as `GX10_RELEASE_REVISION`. Do not deploy an uncommitted working tree.

```bash
sudo git clone --branch openspec/gx10-full-operation-observability \
  https://github.com/jankneumann/agentic-content-analyzer.git /opt/aca
sudo git -C /opt/aca rev-parse HEAD
sudo chown -R root:root /opt/aca
sudo chmod -R go-w /opt/aca
cd /opt/aca && sudo -H uv sync --frozen
```

Create `/etc/aca/gx10-images.env` as root-owned `0600`. It controls what may
execute, so treat it as protected even though it contains no credential.

```bash
sudo install -m 0600 -o root -g root /dev/null /etc/aca/gx10-images.env
sudoedit /etc/aca/gx10-images.env
```

At minimum it defines:

```text
GX10_APP_IMAGE=registry.example/aca:<approved-tag>@sha256:<64-hex-digest>
GX10_SQUID_DIGEST=<64-hex-digest>
GX10_LANGFUSE_WORKER_DIGEST=<64-hex-digest>
```

The image validation implementation must identify an approved **published**
Squid tag and prove it resolves to the configured digest. Do not insert an
arbitrary Squid digest to bypass the current missing-tag failure. Verify that
each reference is a `linux/arm64` image before any maintenance window:

```bash
skopeo inspect --format '{{.Digest}} {{.Os}}/{{.Architecture}}' docker://registry.example/namespace/image:tag
sudo podman pull registry.example/namespace/image:tag@sha256:<64-hex-digest>
sudo podman image inspect registry.example/namespace/image:tag@sha256:<64-hex-digest> --format '{{.Digest}} {{.Os}}/{{.Architecture}}'
```

## 5. Convert the runtime to Podman

This is required source-controlled work, not a host-only substitution. These
surfaces currently invoke Docker and must be converted and tested together:

| Surface | Required Podman change |
| --- | --- |
| `deploy/gx10/systemd/aca-gx10.service` | Rootful Podman start/stop and bounded explicit readiness polling; do not rely on Docker Compose `--wait`. |
| secret, proxy-policy, and OpenBao units | Remove `docker.service` dependencies and use the same Podman execution path. |
| `scripts/gx10/*.sh` | Replace `docker compose`, `docker run`, and `docker buildx` with a single wrapper, `podman run`, and `skopeo inspect`. |
| clean-stack/recovery gates | Preserve real restart, health, and persistence evidence under Podman. |

Do **not** use `podman-docker` as the production answer. It hides incompatible
Buildx and Compose semantics, which can make a validation appear successful
without proving the intended behavior.

### 5.1 Use one wrapper

Add and review `/opt/aca/scripts/gx10/podman-compose.sh` in the repository:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/podman-compose -p aca-gx10 -f /opt/aca/docker-compose.gx10.yml "$@"
```

Every GX-10 unit and script uses this wrapper. It must not read secrets or open
a shell. Prove the selected `podman-compose` version can render the current
networks, bind mounts, health checks, and environment files:

```bash
cd /opt/aca
sudo scripts/gx10/podman-compose.sh config >/run/aca/gx10/rendered-compose.yml
sudo chmod 0600 /run/aca/gx10/rendered-compose.yml
```

If it cannot honor `depends_on` health conditions, start stateful services first
and gate every application role with `gx10-role-ready`. Never replace readiness
with arbitrary sleeps.

### 5.2 Convert units and verify them

After the wrapper changes are committed, copy the units and edit only their
tracked Podman equivalents:

```bash
sudo install -m 0644 /opt/aca/deploy/gx10/systemd/aca-gx10*.service /etc/systemd/system/
sudo install -m 0644 /opt/aca/deploy/gx10/systemd/aca-gx10*.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/aca-gx10*.service
sudo rg -n '\bdocker\b' /etc/systemd/system/aca-gx10*.service /etc/systemd/system/aca-gx10*.timer && exit 1 || true
sudo systemctl daemon-reload
```

Preserve `LoadCredential=`, `UMask=0077`, `ProtectSystem=`,
`ReadWritePaths=`, and `NoNewPrivileges=`. Quadlet is acceptable only as a full
reviewed replacement: every network, volume, health dependency, secret, and
restart behavior must be carried over. Do not mix a partial Quadlet conversion
with a Compose-managed production stack.

## 6. OpenBao, secrets, and network policy

Create `/etc/aca/gx10/bao-seed.json` from an offline secret-generation process
and install it mode `0600`. It contains `runtime`, `operator`, `proxy`, and
`backup` objects. The checked-in ceremony validates distinct database passwords,
safe 32+ character Redis/proxy credentials, a real bcrypt Caddy hash, release
and authority values, and an active plus retained `age` recipient/identity set.

```bash
