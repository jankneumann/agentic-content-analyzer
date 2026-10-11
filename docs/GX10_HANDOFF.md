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

### 1–3. Langfuse wipe, sliced pruner, local generations — done 2026-10-10

Wiped; the stack rebuilt with identical keys; `prune-traces` authenticated
and found 0 expired traces with no 422; the next backup pruned 15 generations
(112 GB → 7.3 GB). A post-wipe generation is ~233 MB (ClickHouse 134 MB,
application Postgres 99 MB). ClickHouse will regrow toward its 30-day window.

The first wipe attempt failed with "Directory not empty": the minutely storage
monitor `Requires=aca-gx10.service`, so it restarted the stack within a minute
of `make stop` and ClickHouse/MinIO wrote into the tree mid-`rm`. Fixed: no
timer-driven unit can start the runtime (backup and restore drill fail loudly
via `ExecStartPre`; the monitor skips quietly via `ExecCondition`), and a
future wipe is one guarded command:

```bash
sudo make -C /opt/aca/deploy/gx10 wipe-langfuse CONFIRM=wipe-langfuse
```

### 4. Off-site backup — done 2026-10-10

Live on **Cloudflare R2**, bucket `aca-gx10-backups`, 30-day lock / 35-day
expiry on `aca/gx10/`. First generation `20261011T004039Z` shipped: 7 objects,
233,166,391 bytes, every size read back. Lock proven: a delete of a probe
object returned `ObjectLockedByBucketPolicy`. From here the 03:00 backup ships
each good generation via `OnSuccess=`; check the first unattended run with
`journalctl -u aca-gx10-backup-offsite`.

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
**bucket lock rule**: locks block delete *and* overwrite, apply to existing
objects, and take precedence over lifecycle rules. A compromised host holding
the token still cannot destroy history younger than the lock.

#### R2 setup, step by step

**A. Bucket** — Cloudflare dashboard → **R2 Object Storage** → **Create
bucket**. Name `aca-gx10-backups`, location *Automatic* (or a hint near the
host), default storage class **Standard** (Infrequent Access charges per read
and has a 30-day minimum — wrong for a bucket a restore drill may read).
Leave public access **off**; no custom domain. Note your **Account ID** from
the R2 overview page (32 hex characters).

**B. Bucket lock rule** — bucket → **Settings** → **Bucket lock rules** →
**Add rule**: name `gx10-generations`, prefix `aca/gx10/`, retention **30
days**. Save. *Prefix, not empty*: an unprefixed rule would also lock anything
else you ever put in the bucket.

**C. Lifecycle rule** — same **Settings** page → **Object lifecycle rules** →
**Add rule**: name `gx10-expire`, prefix `aca/gx10/`, delete objects after
**35 days**. Must exceed the lock: a shorter expiry is silently overridden, so
the bill would be set by the lock, not this rule. Also enable *abort incomplete
multipart uploads after 1 day* if offered — a killed upload otherwise leaves
billable parts behind. Expiry runs within 24 h of the date.

Cost at 35 generations: ~8 GB today (inside the 10 GB free tier); at several
GB per generation as ClickHouse regrows, $0.015/GB-month — single dollars.

**D. API token** — R2 overview → **Account Details** → **API Tokens: Manage**
→ **Create Account API token** (account, not user: it survives your user
account changing). Permission **Object Read & Write**; scope **Apply to
specific buckets only** → `aca-gx10-backups`; TTL *forever* (expiry would
silently stop backups; the lock bounds the damage of a leak instead). Create,
then copy the **Access Key ID** and **Secret Access Key** — the secret is
shown once. Do not paste them into chat, a ticket, or a shell command line.

**E. Store in OpenBao** — prompts for the values (secret hidden), writes
`secret/newsletter/gx10/backup-offsite`, and re-uploads the backup policy,
which the provisioning ceremony only writes at first install:

```bash
sudo git -C /opt/aca pull
sudo /opt/aca/deploy/gx10/openbao/seed-offsite-secret.sh
```

**F. Deploy and ship the current generation**

```bash
sudo make -C /opt/aca/deploy/gx10 install
sudo systemctl start aca-gx10-backup-offsite.service
sudo journalctl -u aca-gx10-backup-offsite -n 20 --no-pager
```

Expect a JSON summary: seven objects `uploaded` (six artifacts + manifest).
Re-running reports them `present` and uploads nothing. In the dashboard the
bucket shows `aca/gx10/<generation>/`.

**G. Prove the lock** — an unlocked bucket looks identical until you need it.
This uploads a throwaway probe object (never a real artifact) and tries to
delete it; the delete **must** be refused:

```bash
sudo systemctl start aca-gx10-backup-secrets.service
sudo /opt/aca/deploy/gx10/openbao/render-offsite-secrets.sh
sudo /opt/aca/.venv/bin/python - <<'PY'
import time; from scripts.gx10.backup.offsite import OffsiteTarget
from pathlib import Path
t = OffsiteTarget.from_file(Path("/run/aca/gx10/backup/offsite.json")); c = t.client()
key = f"{t.prefix}/gx10/lock-probe-{int(time.time())}.txt"  # fresh key: rerunnable
c.put_object(Bucket=t.bucket, Key=key, Body=b"probe")
try:
    c.delete_object(Bucket=t.bucket, Key=key); print("FAIL: delete succeeded -- lock is NOT active")
except Exception as exc:
    print("OK: delete refused --", type(exc).__name__, exc)
PY
sudo rm -f /run/aca/gx10/backup/offsite.json
```

(Run it from `/opt/aca` so `scripts.` imports.) The probe expires with the
lifecycle rule. From then on the 03:00 backup ships automatically; a failure
fires `aca-gx10-maintenance-alert@aca-gx10-backup-offsite.service`.

Restore path: download a generation directory (`aws s3 cp --recursive
--endpoint-url ...` or rclone) into an artifacts dir and point
`aca-gx10-restore-drill` at it — the uploaded manifest is the same file the
drill reads.

### 5. Stream the backup pipeline — backup done; restore drill still buffers

The scheduled backup now runs `producer | age --encrypt` straight to disk
(`stream_component` in `scripts/gx10/backup/runtime.py`): memory is one 8 MiB
chunk whatever the component size, both exit codes are checked, the quota is
enforced mid-stream, and an artifact appears under its real name only after
fsync + rename. A test streams 256 MiB and asserts peak RSS grows < 64 MiB.

**Still buffered: the restore drill.** `run_isolated_restore` reads each
artifact, decrypts it in memory and pipes it to the restore command, bounded
by `MAX_COMPONENT_BYTES` (8 GiB). Once ClickHouse regrows past that, the
weekly drill fails that component (alone) and alerts. The fix mirrors the
backup: `age --decrypt` (identity via `/proc/self/fd`, as `AgeCommandAdapter`
does) piped into the restore command.

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

1. ~~R2 or S3~~ — R2, provisioned and lock-proven 2026-10-10.
2. Does the coordinator need a LAN route through Caddy in addition to the
   tunnel, or is the tunnel the only intended path?
3. Merge `feat/gx10-coordinator-deployment`, or hold it until after a successful
   install?
