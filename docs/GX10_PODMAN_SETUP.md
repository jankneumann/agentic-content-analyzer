# GX-10 production setup with Podman

This is the operator runbook for running Agentic Content Analyzer on the GX-10
with **Podman**, not Docker. It covers the `PROFILE=gx10` local-production
stack: PostgreSQL, Redis, FalkorDB, OpenBao, Langfuse, ClickHouse, MinIO, Caddy,
Squid, the API, workers, schedulers, and maintenance services.

> **Status:** The checked-in GX-10 runtime uses rootful Podman through an
> explicit `podman-compose` wrapper, bounded health polling, and ARM64-aware
> `skopeo` provenance checks. The stack remains unaccepted until its real
> clean-stack, native-backup, and soak evidence gates are completed.

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
| Approved published Squid image | `docker.io/ubuntu/squid:6.6-24.04_beta@sha256:6a097f68bae708cedbabd6188d68c7e2e7a38cedd05a176e1cc0ba29e3bbe029` is published for ARM64 and must remain digest-pinned. |
| OpenBao recovery material and first-install seed | Initialization and unseal are operator ceremonies, never normal startup. |
| External-provider credentials | Model, video, mail, and delivery APIs stay external by design. |
| `age` recipient and escrowed decrypt identities | Loss of all identities makes encrypted backups unrecoverable. |
| Maintenance window | Needed for cold-restart, dependency-loss, and native restore evidence. |

Never put secrets in Git, Compose files, shell history, unit command lines, or
chat transcripts.

## Operator targets

`deploy/gx10/Makefile` sequences the reviewed scripts and units so the
recurring host procedures are one command each. It never pulls; run
`sudo git -C /opt/aca pull --ff-only` first, deliberately.

```bash
sudo make -C /opt/aca/deploy/gx10 help
sudo make -C /opt/aca/deploy/gx10 ownership   # data-directory owners, then the preflight
sudo make -C /opt/aca/deploy/gx10 provision   # first-install OpenBao ceremony
sudo make -C /opt/aca/deploy/gx10 image       # build gx10-<sha>, push, print the pin line
sudo make -C /opt/aca/deploy/gx10 start       # install units, sweep containers, start
sudo make -C /opt/aca/deploy/gx10 status
sudo make -C /opt/aca/deploy/gx10 logs SINCE="1 hour ago"
```

The manual blocks below remain the reference for what each target does.

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
sudo install -d -o root -g root -m 0700 /srv/aca/application /srv/aca/caddy-data /srv/aca/caddy-config
sudo install -d -o 999 -g 999 -m 0700 /srv/aca/postgres /srv/aca/langfuse-postgres
sudo install -d -o 999 -g 1000 -m 0700 /srv/aca/redis
sudo install -d -o 999 -g 999 -m 0700 /srv/aca/falkordb
sudo install -d -o 101 -g 101 -m 0700 /srv/aca/clickhouse /srv/aca/clickhouse-logs
sudo install -d -o 60001 -g 60001 -m 0700 /srv/aca/minio
sudo install -d -o 100 -g 1000 -m 0700 /srv/aca/openbao
sudo install -d -o 13 -g 13 -m 0700 /srv/aca/squid-logs
```

Every stateful image in the stack starts as root and drops to its own service
account with `gosu`, `su-exec`, or `setpriv`. That drop needs `CAP_SETUID`,
`CAP_SETGID`, and usually `CAP_CHOWN`; the stack drops every capability, so
each Compose service starts directly as the image's own user and the bind
mount must already carry that ownership. The users below were read from the
pinned digests, not guessed; re-verify them whenever a digest changes.

| Service | Image user | Data paths |
| --- | --- | --- |
| `app-postgres`, `langfuse-postgres` | `999:999` (`postgres`) | `/srv/aca/postgres`, `/srv/aca/langfuse-postgres` |
| `redis` | `999:1000` (`redis`) | `/srv/aca/redis`, reads `/run/aca/gx10/redis/users.acl` |
| `falkordb` | `999:999` (`redis` in this image) | `/srv/aca/falkordb`, reads `/run/aca/gx10/falkordb/users.acl` |
| `clickhouse` | `101:101` (`clickhouse`) | `/srv/aca/clickhouse`, `/srv/aca/clickhouse-logs` |
| `minio` | `60001:60001` (any uid; unallocated on the host) | `/srv/aca/minio` |
| `openbao` | `100:1000` (`openbao`) | `/srv/aca/openbao` |
| `squid` | `13:13` (`proxy`) | `/srv/aca/squid-logs`, reads `/run/aca/gx10/proxy/squid.passwd` |
| `caddy` | root with only `NET_BIND_SERVICE` | `/srv/aca/caddy-data`, `/srv/aca/caddy-config` |

`scripts/gx10/check_persistence_ownership.py` enforces this table before the
runtime, the OpenBao container, and Squid start: it reads the overlay, compares
every `/srv/aca` and `/run/aca/gx10` bind mount with the service's `user:`,
and prints the exact `install -d` or `chown -R` command for each finding.

Rootful Podman shares the host uid space, so a host account with the same
numeric uid (for example `dnsmasq` at 999 or `proxy` at 13 on Ubuntu) can read
that service's data. `install -d` on an existing directory re-applies owner
and mode without recursing; if a directory already holds data written by
another uid, `chown -R` it once to the user in the table.

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
enabled: `clickhouse-backup`, MinIO `mc`, and the OpenBao `bao` client. FalkorDB
needs no native tool: it is backed up as an offline tar of its RDB/AOF data
directory, and `redis-cli` inside the container is enough for inspection. Use verified ARM64 releases; do not use an unreviewed `curl | sh`
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

Every image reference, including this one, must name its registry host. The
rootful host defines no unqualified-search registries, and Podman does not apply
short-name aliases to digested references, so `ubuntu/squid@sha256:...` is
refused while `docker.io/ubuntu/squid:...@sha256:...` pulls. Tags must be exact
releases (`langfuse/langfuse-worker:3.225.5`, never `:3`): the image-pins gate
re-resolves each tag against the registry and refuses to start when the tag has
moved away from the recorded digest, which a major-version tag does on every
upstream patch release. Bump the tag and the digest together, after review.

The image validation implementation must identify an approved **published**
Squid tag and prove it resolves to the configured digest. Do not insert an
arbitrary Squid digest to bypass the current missing-tag failure. Verify that
each reference is a `linux/arm64` image before any maintenance window:

```bash
skopeo inspect --format '{{.Digest}} {{.Os}}/{{.Architecture}}' docker://registry.example/namespace/image:tag
sudo podman pull registry.example/namespace/image:tag@sha256:<64-hex-digest>
sudo podman image inspect registry.example/namespace/image:tag@sha256:<64-hex-digest> --format '{{.Digest}} {{.Os}}/{{.Architecture}}'
```

## 5. Use the checked-in Podman runtime

This is source-controlled, not a host-only substitution. The following Podman
contract is already checked in and must be preserved as the runtime evolves:

| Surface | Required Podman change |
| --- | --- |
| `deploy/gx10/systemd/aca-gx10.service` | Rootful Podman start/stop and bounded explicit readiness polling; do not rely on a Compose `--wait` extension. |
| secret, proxy-policy, and OpenBao units | Remove `docker.service` dependencies and use the same Podman execution path. |
| `scripts/gx10/*.sh` | Replace `docker compose`, `docker run`, and `docker buildx` with a single wrapper, `podman run`, and `skopeo inspect`. |
| clean-stack/recovery gates | Preserve real restart, health, and persistence evidence under Podman. |

Do **not** use `podman-docker` as the production answer. It hides incompatible
Buildx and Compose semantics, which can make a validation appear successful
without proving the intended behavior.

### 5.1 One wrapper, no implicit provider

The checked-in `/opt/aca/scripts/gx10/podman-compose.sh` is the only Compose
entry point:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/podman-compose -p aca-gx10 -f /opt/aca/docker-compose.gx10.yml "$@"
```

Every GX-10 unit and script uses this wrapper. It must not read secrets or open
a shell. After image policy and rendered secrets exist, prove the selected `podman-compose` version can render the current
networks, bind mounts, health checks, and environment files:

```bash
cd /opt/aca
sudo scripts/gx10/podman-compose.sh config >/run/aca/gx10/rendered-compose.yml
sudo chmod 0600 /run/aca/gx10/rendered-compose.yml
```

The runtime calls `podman-runtime.sh up`, which recreates every container
(Podman stores `depends_on` by container ID, so a stack that was partially
recreated cannot be started incrementally; all state lives under `/srv/aca`)
and then polls every required container's health with a bounded timeout.
Never replace that readiness proof with sleeps.

### 5.2 Convert units and verify them

Copy the reviewed units; do not hand-edit substitutes outside version control:

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

Rootful Podman runs in the credential-free
`aca-gx10-openbao-container.service`. The provisioning and secret-rendering
units depend on it but never invoke Podman themselves, so they retain
`ProtectSystem=strict` without exposing Podman's graph, Libpod, Netavark, or
runtime namespace paths inside credential-bearing processes. The credential-free container unit uses the same minimal systemd boundary as
the main rootful Podman runtime. `ProtectHome` and `ProtectSystem` are not
compatible with image extraction because container layers legitimately contain
`/home`, `/usr`, and other root-level paths. A fail-closed post-start check
requires the OpenBao container to exist and be running before provisioning.

Several containers bind-mount single files from `/opt/aca` (`openbao.hcl`,
`squid.conf`, `allowed-domains.txt`, the Caddyfile, and the two readiness
scripts). `git pull` writes a changed file as a new inode, but a running
container keeps the inode it mounted, so it continues to execute the old
content. After pulling a change to any bind-mounted file, remove the affected
container and let its unit recreate it, for example
`sudo podman rm -f aca-gx10_squid_1` before restarting
`aca-gx10-proxy-policy.service`.

`aca-gx10-openbao-container.service` is a `oneshot` that does not stay
`active` after success: its start is idempotent (`ensure_service.sh`), so every
dependent start re-runs it and recreates the container if the runtime's sweep
removed it. `systemctl status` therefore shows it `inactive (dead)` between
runs; that is expected. The secrets, provision, and runtime chains all pull it
in through `Requires=`.

## 6. OpenBao, secrets, and network policy

The public origin has no default. Create `/etc/aca/gx10-public.env` (root,
`0600`) with the https origin operators will browse, for example:

```text
GX10_PUBLIC_ORIGIN=https://gx10.home.arpa
```

The application refuses a Langfuse public URL whose host is `localhost`,
`.local`, or `.internal`, and the secrets renderer enforces the same rule, so
pick a name outside those suffixes (`home.arpa` is reserved for exactly this).
Re-run `make secrets` after changing it.

No service publishes a host port. Caddy holds the fixed address `10.89.1.250`
on the declared `10.89.1.0/24` application subnet and listens on 443 there.
Map the host of `GX10_PUBLIC_ORIGIN` to that address in `/etc/hosts` on the
GX-10 host (for example `10.89.1.250 gx10.home.arpa`) and open
`https://gx10.home.arpa/`; from another machine, tunnel with
`ssh -L 8443:10.89.1.250:443 gx10` and map the name to `127.0.0.1` locally.

OpenBao publishes no host port. The stateful network is `internal: true`, and
netavark installs no port-forwarding rules for internal networks; Podman still
binds the published host port as a reservation and hands that socket to
`conmon`, so a loopback publish accepts TCP and then hangs with no reply. The
service instead holds the fixed address `10.89.0.250` on the declared
`10.89.0.0/24` stateful subnet, and the provisioning, secrets, and backup
units dial `http://10.89.0.250:8200/v1` directly over the bridge. Host-local
processes can reach it because the host owns the bridge gateway; nothing else
can, because the network has no forwarding rules. Containers keep resolving
the `openbao` alias.

Create `/etc/aca/gx10/bao-seed.json` from an offline secret-generation process
and install it mode `0600`. It contains `runtime`, `operator`, `proxy`, and
`backup` objects. The checked-in ceremony validates distinct database passwords,
safe 32+ character Redis/proxy credentials, a real bcrypt Caddy hash, release
and authority values, and an active plus retained `age` recipient/identity set.

For self-hosted Langfuse, the `runtime` object must also contain stable
`langfuse_init_org_id`, `langfuse_init_org_name`, `langfuse_init_project_id`,
`langfuse_init_project_name`, `langfuse_init_user_email`,
`langfuse_init_user_name`, and a 32+ character
`langfuse_init_user_password`. The renderer supplies these along with the
seeded public/secret API keys to Langfuse headless initialization, so the
application keys always belong to a real local Langfuse project. Treat the
initial user password as a password-manager record; never print it or add it
to a command line.

```bash
