# GX-10 Handoff

State of the `gx10-ec87` host as of 2026-10-21, the coordinator install runbook,
and every task left open. Written to be picked up cold.

Read [CASE_STUDIES.md → GX-10 Production Bring-Up](CASE_STUDIES.md#gx-10-production-bring-up-septemberoctober-2026)
first. It lists the specific ways this host punishes assumptions, and both
deployments are shaped by it.

---

## Where things stand

| | |
|---|---|
| Analyzer repo | `openspec/gx10-full-operation-observability`, pushed. Still **not merged to `main`** (88+ commits) |
| Deployed at `/opt/aca` | `dbe14da8`. The backup-freshness commit after it needs `git pull` + `make install` |
| Coordinator repo | `feat/gx10-coordinator-deployment` @ `6b0dfca5`, pushed, **not merged, not deployed** |
| Analyzer runtime | Up since 2026-10-20 ~21:30 EDT after an 8-day outage. All units enabled for boot |
| Backup | Local + R2 green; catch-up generation `20261021T013318Z` (4.8 GB) |
| Restore drill | **First ever green run 2026-10-20.** It proves decrypt + unpack only — see task 5 |

The analyzer stack runs green: 15 containers healthy (OpenBao included),
Langfuse receiving traces, and the Langfuse pruner deployed and scheduled.
**It has not yet survived a real reboot since the fixes below** — do one in a
quiet window and check `make status`.

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

### 0. The 2026-10-12 reboot outage — fixed 2026-10-20, reboot not yet re-proven

The host rebooted on 2026-10-12 at 14:40 and **the analyzer stayed down for
eight days**: no ingestion, no digests, no backups, no host firewall. Nothing
alerted. Every cause was something the manual bring-up had done by hand and
the repo did not:

| Cause | Symptom | Fix |
|---|---|---|
| `make install` never ran `systemctl enable` | Every unit `disabled`; nothing started at boot | `install` enables every unit with `[Install]` (`dcf2770f`) |
| `/run/aca/gx10` made by hand once; `/run` is a tmpfs | image-pins `226/NAMESPACE` (`ReadWritePaths=`), so OpenBao (`Requires=` it) never started | `deploy/gx10/tmpfiles/aca-gx10.conf`, applied by `install` and at boot |
| Restore drill appends stdout inside its own `StateDirectory=`; systemd opens output **before** creating state dirs | "Failed to set up standard output" — **every drill since install**, Oct 5 and 12 included | Same tmpfiles file creates `restore-evidence` |
| Drill `--isolated-root` was its `RuntimeDirectory=`, which systemd pre-creates | "dedicated restore root must not already exist" — the drill could never pass | Root is now `.../restore-drill/isolated` (`6c910229`) |
| Trace probe read `langfuse.traces`; Langfuse migrates into `default` (it gets no `CLICKHOUSE_DB`; the server's `CLICKHOUSE_DB=langfuse` only creates an empty DB) | `langfuse_trace_metadata_missing` with 513 traces present | Probe and `native_persistence_evidence.sh` query `default.traces` (`dbe14da8`) |
| No check for a backup that never ran | 8 days, zero alerts: `OnFailure=` needs a run to fail | `aca-gx10-backup-freshness.timer`, hourly, 36 h limit, runtime-independent |

Each has a regression test in `tests/deployment/gx10/`. Lessons:

- **A fresh boot is the first time the host runs exactly what is in the repo.**
  Anything created by hand during bring-up — a directory, a `start`, an enable —
  is a reboot bug waiting.
- **The bugs were stacked.** Each fix exposed the next; the drill needed three
  before it reached the code that does the work.
- **`aca-gx10-maintenance-alert@` only writes a syslog line** (`logger -p
  daemon.err`). It fired for every failed drill and nobody saw it. Until it
  delivers somewhere a person looks (task 8), *every* alert on this host,
  including the new freshness one, is a journal entry.

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

### 5. Stream the backup pipeline — backup done; restore drill still buffers, and is shallow

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

**More urgent than it looked.** ClickHouse regrew from 134 MB (Oct 10) to
4.5 GB+ (Oct 20); the generation is 4.8 GB. Two limits are near: the 8 GiB
in-memory decrypt bound, and the isolated root living on the **13 GB `/run`
tmpfs** (i.e. in RAM). Move the root to disk in the same change.

**The drill proves less than its name** (read `scripts/gx10/backup/component.sh`):

| Component | "restore" | "validate" |
|---|---|---|
| Both Postgres | `pg_restore --file=…sql` — dump converted to a SQL **text file** | file non-empty |
| ClickHouse, MinIO, FalkorDB, config | `tar -xf` into a directory | directory non-empty |
| Metadata probes | run against **production** containers, not the restore | — |

No database is ever started on restored data, so the reported 20 s RTO is
unpack time. A green drill means "artifacts decrypt and unpack, and production
holds data" — worth a lot, but not a restore. Do the real restore (throwaway
`paradedb`/`clickhouse` on `$target/data`, probes pointed at them) as an
OpenSpec change together with the streaming fix; both rewrite the same path.

### 6. Serve the kanban frontend — to be built from agentic-coding-tools

Owner: a session started in `agentic-coding-tools` (branch
`feat/gx10-coordinator-deployment`). Depends on Part 1: the route proxies to
`coordinator-api`, so nothing can be verified live before the coordinator is
installed.

**Do not bake the API key.** `apps/kanban-viz/src/App.tsx` reads
`VITE_COORDINATOR_API_KEY` at *build* time, so it ships inside the JS bundle;
anyone who can load the page can read it and call the coordinator API
directly. Decided 2026-10-10: **Caddy injects the key** instead.

Design:

- Build with `VITE_COORDINATOR_URL=/kanban/api` and no API key. Vite also
  needs `base: "/kanban/"` (or `--base /kanban/`), or the built `index.html`
  requests `/assets/...` and gets the analyzer API instead.
- Analyzer `deploy/gx10/Caddyfile`, inside the existing site block (already
  behind `basic_auth`), ahead of the catch-all `handle`:
  - `handle_path /kanban/api/*` → `reverse_proxy coordinator-api:<port>` with
    `header_up X-API-Key {$KANBAN_COORDINATOR_API_KEY}` and
    `flush_interval -1` (the board uses SSE via `/events/auth`; a buffering
    proxy makes it hang silently).
  - `handle_path /kanban/*` → `root` + `file_server` over the built `dist/`,
    with `try_files {path} /index.html`.
  - Strip any client-sent `X-API-Key` (`header_up -X-API-Key` before setting
    it), so the browser cannot choose the identity.
- Mount `dist/` read-only into the caddy container, and add a host build step
  (make target) that produces it from a pinned checkout. `apps/kanban-viz`
  intentionally has no Dockerfile.
- Use a **dedicated kanban identity** in `coordination_api_key_identities`, so
  it can be revoked alone. The board writes (labels, agent kicks), so it needs
  write scope.

**Open decision: where Caddy reads the key.** Caddy is in the analyzer stack,
whose AppRole reads only `secret/newsletter/gx10/*`; the coordinator's reads
only `secret/coordinator/gx10/*`. Either store a copy at
`secret/newsletter/gx10/runtime` as `kanban_coordinator_api_key` (the
analyzer's `render-secrets.sh` writes it to `caddy.env`; the AppRoles stay
separate, at the cost of two places to rotate), or widen the analyzer policy to
read that one field from the coordinator path.

Resolves open question 2 below: yes, there will be a LAN route to the
coordinator API, behind the site's basic auth, scoped to the kanban identity.

### 7. Pre-existing test breakage (not from this work)

13 failures in `tests/queue/` and 59 in `tests/services/` (the latter need a
live PostgreSQL this host does not provide for tests). Verified identical with
all changed files reverted to `HEAD`. Do that comparison before chasing any
suite failure here — it takes a minute and prevents both chasing someone else's
breakage and shipping your own under cover of it.

---

### 8. Deliver maintenance alerts to a person

`aca-gx10-maintenance-alert@.service` runs `logger` and nothing else. Wire it to
something that reaches a human (the app's notification channel, ntfy, mail).
It must not depend on the runtime: the alerts that matter most fire when the
runtime is down.

### 9. Backfill the 2026-10-12 → 10-20 digest gap

The scheduler resumed on restart but does not backfill missed periods. Run the
daily pipeline for each missed day (`aca pipeline run --period daily
--period-start … --period-end … --wait`) once ingestion has caught up.

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
2. ~~LAN route through Caddy?~~ Yes, for the kanban board only (task 6), behind
   basic auth with a dedicated key Caddy injects.
3. Merge `feat/gx10-coordinator-deployment`, or hold it until after a successful
   install?
