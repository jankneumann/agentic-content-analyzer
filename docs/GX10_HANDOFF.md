# GX-10 Handoff

State of the `gx10-ec87` host as of 2026-10-10, the coordinator install runbook,
and every task left open. Written to be picked up cold.

Read [CASE_STUDIES.md → GX-10 Production Bring-Up](CASE_STUDIES.md#gx-10-production-bring-up-septemberoctober-2026)
first. It lists the specific ways this host punishes assumptions, and both
deployments are shaped by it.

---

## Where things stand

| | |
|---|---|
| Analyzer repo | `openspec/gx10-full-operation-observability` @ `3210c834`, clean, pushed |
| Deployed at `/opt/aca` | `b0a89c2c` — one commit behind (`3210c834` is docs only, no rebuild needed) |
| Coordinator repo | `feat/gx10-coordinator-deployment` @ `6b0dfca5`, pushed, **not merged, not deployed** |
| Analyzer runtime | Up. Langfuse healthy, `app-postgres` reachable at `10.89.0.251` |

The analyzer stack runs green: 15 containers healthy, backup produces six
verified encrypted artifacts, and the Langfuse pruner is deployed and scheduled.

**Container IPs move on every restart.** Only `app-postgres` (`10.89.0.251`),
`openbao` (`10.89.0.250`) and `caddy` (`10.89.1.250`) are fixed. Rescan rather
than reusing a noted address.

---

## Part 1 — Coordinator install

Everything is written and tested (19 deployment tests pass); nothing is
deployed. The design: a separate compose project `aca-gx10-coord` joining the
analyzer's networks as external, reusing its Langfuse, OpenBao and Squid. Three
containers — `coordinator-postgres`, `coordinator-api`, `cloudflared`.

Full detail in `agentic-coding-tools/deploy/gx10/README.md`.

### Prerequisites (need credentials or a UI — cannot be scripted)

1. **A Langfuse project for the coordinator.** The analyzer's headless init
   seeds exactly one project, so the second is created once via the Langfuse
   API or UI. Store its keys at `secret/coordinator/gx10/runtime` as
   `langfuse_public_key` / `langfuse_secret_key`.
2. **An OpenBao AppRole** scoped to read `secret/coordinator/gx10/*` only —
   **not** the analyzer's path. Role id and secret id to
   `/etc/aca/gx10/coordinator-role-id` and `.../coordinator-secret-id`, 0600
   root. They are loaded as systemd credentials, so they never reach the
   environment or the process table.
3. **The remaining secrets** at the same path: `postgres_password`,
   `coordination_api_keys`, `coordination_api_key_identities`,
   `coordination_api_key`, `sse_signing_key`.
4. **A Cloudflare tunnel** — `cloudflared tunnel create gx10-coordinator` —
   credentials JSON at `/run/aca/gx10/cloudflared/credentials.json` (0600), and
   `GX10_COORD_TUNNEL_CONFIG` pointing at a config whose **only** ingress rule
   is the coordinator API. The renderer greps it and refuses anything naming
   port 8200, 5432, 8123, 9000 or 8082.
5. **A Cloudflare Access application** on `coord.<domain>` with a service token
   for cloud agents. Without it the tunnel publishes the API with only
   `X-API-Key` in front — the weak version of this design, and indistinguishable
   from the strong one until you test an unauthenticated request. **Test one.**
6. **A firewall rule** for the tunnel's egress. `cloudflared` holds an outbound
   connection that does not pass through Squid: a deliberate, documented
   exception to the egress policy, which is why it sits alone on the egress
   network with no route to `stateful`.

### Bring-up

```bash
sudo git -C /opt/agentic-coding-tools pull       # or clone the branch there first
sudo make -C /opt/agentic-coding-tools/deploy/gx10 image
sudo nano /etc/aca/gx10-images.env               # paste GX10_COORD_IMAGE
#   also needs GX10_COORD_POSTGRES_IMAGE and GX10_CLOUDFLARED_IMAGE pinned
sudo make -C /opt/agentic-coding-tools/deploy/gx10 ownership
sudo make -C /opt/agentic-coding-tools/deploy/gx10 start
sudo make -C /opt/agentic-coding-tools/deploy/gx10 status
```

`GX10_COORD_POSTGRES_IMAGE` can reuse the digest the analyzer already proves:
`docker.io/paradedb/paradedb:0.25.9-pg17@sha256:8da5d202fe31875af32a49e802ce17cfbc146b0672306f4109809efee1e6f916`.

### Two things that could not be verified from a non-root shell

Both surface on the first `make start`, and `coordinator-runtime.sh` dumps the
last 40 log lines per unhealthy service, so the failure arrives with evidence.

- **Whether podman-compose 1.0.6 honours `external: true` + `name:`.** If it
  creates its own networks instead of joining, the coordinator comes up unable
  to see Langfuse — a working stack wired to nothing. `coordinator-runtime.sh`
  pre-checks that both analyzer networks exist, but cannot check that
  podman-compose *joined* them. Verify with
  `podman inspect aca-gx10-coord_coordinator-api_1 --format '{{json .NetworkSettings.Networks}}'`.
- **Whether the coordinator's migrations run clean on PostgreSQL 17 /
  ParadeDB 0.25.9.** Its own compose pins `v0.22.2`. Migrations run
  automatically at API startup, so a failure appears as the API never becoming
  healthy. If it breaks, pin `GX10_COORD_POSTGRES_IMAGE` to a reviewed 0.22
  digest instead of reusing the analyzer's.

---

## Part 2 — Open tasks

### 1. Wipe the Langfuse backlog — reclaims ~44 GB

Not yet confirmed done. The pruner prevents recurrence but cannot clear a
backlog of ~251k hour-old traces at a 30-day window, and grinding it through
the legacy API is hours of ClickHouse churn against an endpoint its own authors
call slow.

```bash
sudo make -C /opt/aca/deploy/gx10 stop
sudo rm -rf /srv/aca/clickhouse
sudo rm -rf /srv/aca/clickhouse-logs
sudo rm -rf /srv/aca/minio
sudo rm -rf /srv/aca/langfuse-postgres
sudo make -C /opt/aca/deploy/gx10 ownership   # recreates + preflight
sudo make -C /opt/aca/deploy/gx10 start
```

**Never glob this.** `/srv/aca/postgres` is the *application* database and sits
one directory from `/srv/aca/langfuse-postgres`; `rm -rf /srv/aca/*postgres*`
takes both. Keep: `postgres`, `application`, `falkordb`, `openbao`, `redis`,
`caddy-*`, `squid-logs`.

Safe because headless init restores the org, project and **both API keys** from
OpenBao — Langfuse rebuilds with identical credentials.

### 2. Verify the sliced pruner

`b0a89c2c` is pulled but its result is unreported. After a rebuild:

```bash
sudo podman exec aca-gx10_maintenance_1 \
  aca telemetry prune-traces --older-than-days 1 --slice-hours 1
```

Dry run; deletes nothing. Expect a cutoff and a count. History: `page=N` died
immediately, the keyset cursor reached 2108 traces, and slicing both ends plus
halving on 422 is the current state. If a 422 still appears, the message now
carries the server's own explanation.

### 3. Backup generations: 112 GB → 7

`/var/lib/aca/gx10/backups` holds 112 GB. The next successful `aca backup run`
prunes to `--keep-generations 7`. No action beyond letting it run.

### 4. Off-site backup — code done, R2 not yet provisioned

Decision made: **Cloudflare R2**. Code is on this branch; nothing is deployed.

How it works: after a successful local run, `OnSuccess=` on
`aca-gx10-backup.service` starts `aca-gx10-backup-offsite.service`. That
unit renders the bucket keys from `secret/newsletter/gx10/backup-offsite` into
`/run/aca/gx10/backup/offsite.json` (removed on stop), then
`scripts/gx10/backup/offsite.py`:

- re-hashes every artifact against the local manifest, refusing anything that
  rotted on disk or did not succeed;
- uploads to `<prefix>/gx10/<generation>/<component>-<generation>.age`;
- never overwrites a key (same size = resumed run, different size = error);
- reads each object's size back, and writes `manifest.json` **last**, so a
  generation with an off-site manifest is complete.

Only the newest generation ships. A missed day is not backfilled: the next
day's generation goes instead, and the failure alerts via `OnFailure=`.

**R2 tokens cannot be write-without-delete.** Immutability comes from a
**bucket lock rule** instead, so a compromised host still cannot destroy
history. Steps (dashboard or `wrangler`):

1. Create bucket `aca-gx10-backups` (location hint near the host).
2. Bucket lock rule on prefix `aca/gx10/`, retention **30 days**.
3. Lifecycle rule on prefix `aca/gx10/`: delete objects after **35 days**
   (must exceed the lock). ~35 generations at a few hundred MB each fits the
   10 GB free tier only *after* task 1's Langfuse wipe — do that first.
4. API token: **Object Read & Write**, scoped to this one bucket only.
5. Seed OpenBao (admin token), then re-upload the backup policy, which
   `provision-first-install.sh` only writes once:

   ```bash
   bao kv put secret/newsletter/gx10/backup-offsite \
     endpoint=https://<account-id>.r2.cloudflarestorage.com \
     bucket=aca-gx10-backups access_key_id=... secret_access_key=...
   bao policy write aca-gx10-backup /opt/aca/deploy/gx10/openbao/aca-gx10-backup.hcl
   ```
6. Deploy and prove it:

   ```bash
   sudo git -C /opt/aca pull && sudo make -C /opt/aca/deploy/gx10 install
   sudo systemctl start aca-gx10-backup-offsite.service   # ships the current generation
   sudo journalctl -u aca-gx10-backup-offsite -n 20
   ```
   Then try to delete one uploaded object with the token: the lock rule must
   refuse it. **Test this** — an unlocked bucket looks identical until you need it.

Restore path: download a generation directory (`aws s3 cp --recursive
--endpoint-url ...` or rclone) into an artifacts dir and point
`aca-gx10-restore-drill` at it — the uploaded manifest is the same file the
drill reads.

### 5. Stream the backup pipeline

Each component is currently built, encrypted and held in memory — buffered
twice — which OOM-killed a run. The per-component 8 GiB guard
(`MAX_COMPONENT_BYTES`) is a band-aid; the real fix is streaming tar → age →
disk. Needed before ClickHouse grows again.

### 6. Serve the kanban frontend

`apps/kanban-viz` builds to `dist/` and has no Dockerfile — intentionally.
Needs a Caddy route in the analyzer's Caddyfile serving those static files, and
a build step producing them on the host. Not yet written.

### 7. Pre-existing test breakage (not from this work)

13 failures in `tests/queue/` and 59 in `tests/services/` (the latter need a
live PostgreSQL this host does not provide for tests). Verified identical with
all changed files reverted to `HEAD`. Do that comparison before chasing any
suite failure here — it takes a minute and prevents both chasing someone else's
breakage and shipping your own under cover of it.

---

## Decisions already made (do not re-litigate without reason)

- **Separate compose project** for the coordinator, not an extension of
  `docker-compose.gx10.yml`. Independent restarts in the direction that matters.
  The analyzer owns the networks, so `PartOf=aca-gx10.service` means stopping it
  stops the coordinator — unavoidable while sharing networks, and explicit.
- **Cloudflare tunnel over Tailscale** for the agent-facing API. Tailscale is
  already on this host and is the right path for MCP and OpenBao, but cloud
  agents cannot join a tailnet. Identity has to live in a header because the
  caller is someone else's ephemeral sandbox. Tailscale Funnel was considered
  and rejected: it has no auth layer of its own.
- **Its own Langfuse project**, so coordinator traces and retention are separate
  from ingestion.
- **Its own Postgres instance**, not a second database in the analyzer's server:
  the coordinator auto-runs migrations at startup, and a shared server puts that
  auto-migrator one connection string away from the analyzer's data.
- **ParadeDB over stock Postgres** for the analyzer (pgvector + BM25 built in).
- **Destination deny-list over domain allow-list** in Squid: a general
  content-ingestion system cannot enumerate its reachable hosts in advance.

## Open questions

1. ~~R2 or S3~~ — R2 chosen. Still needed: account id, the bucket token, and
   confirmation of the 30-day lock / 35-day expiry retention.
2. Does the coordinator need a LAN route through Caddy in addition to the
   tunnel, or is the tunnel the only intended path?
3. Merge `feat/gx10-coordinator-deployment`, or hold it until after a successful
   install?
