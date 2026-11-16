# GX-10 update runbook

How to move the running gx-10 stack to a newer commit on `main`. The gx-10 is the
only production deployment: Railway was retired on 2026-11-15 (see
[GX10_HANDOFF.md](../GX10_HANDOFF.md)).

This covers a routine update of an already-provisioned host. A first install is
[GX10_PODMAN_SETUP.md](../GX10_PODMAN_SETUP.md). Read
[CASE_STUDIES.md → GX-10 Production Bring-Up](../CASE_STUDIES.md#gx-10-production-bring-up-septemberoctober-2026)
before improvising any step.

**Doing the next update from `dbe14da8`?** Read
[the one-time steps](#one-time-steps-for-the-update-from-dbe14da8) first. Two
of them must happen between the pull and the restart.

## What an update changes

| Piece | Updated by | Step |
|---|---|---|
| Repository at `/opt/aca` (scripts, units, compose file) | `git pull` | 3 |
| Host venv `/opt/aca/.venv` (backup and maintenance units run it) | `uv sync --frozen` | 3 |
| App image for `api`, `worker`, `scheduler`, `maintenance` | `make image` + pin + `make image-pins` | 4 |
| systemd units, timers, tmpfiles | `make install` | 5 |
| Rendered runtime secrets | `aca-gx10-secrets.service` | 6 |
| Database schema | `alembic upgrade head`, run by `aca-gx10.service` on start | 6 |

Skip a step and the host refuses to run, by design:
- **Image left unpinned:** `aca-gx10-image-pins.service` rejects a commit whose
  image is not pinned.
- **Units not reinstalled:** `check_unit_current.sh` refuses to start a unit
  whose installed definition differs from the one in `/opt/aca`.

All commands run on the gx-10 as a user with `sudo`.

## Before you start

- The target commit is green in CI on `main` (from a workstation:
  `gh run list --branch main --limit 3`).
- `sudo make -C /opt/aca/deploy/gx10 status` shows every unit active. Fix a
  degraded stack before updating it, or you cannot tell which problems the
  update caused.
- `/opt/aca` tracks `main`. This prints `+refs/heads/*:...` or a line naming
  `main`:

  ```bash
  git -C /opt/aca config --get-all remote.origin.fetch
  ```

  If it names only a feature branch, see the one-time steps below.
- Plan for a few minutes of API downtime in step 6. Pick a window with no
  pipeline run in progress.

## 1. Record the rollback point

```bash
sudo install -d -m 0700 /var/lib/aca/gx10/rollback
sudo git -C /opt/aca rev-parse HEAD | sudo tee /var/lib/aca/gx10/rollback/revision
sudo cp -p /etc/aca/gx10-images.env /var/lib/aca/gx10/rollback/gx10-images.env
sudo podman exec aca-gx10_api_1 alembic current | sudo tee /var/lib/aca/gx10/rollback/alembic-current
```

## 2. Take a backup

```bash
sudo systemctl start aca-gx10-backup.service        # blocks until the backup finishes
systemctl show -p Result --value aca-gx10-backup.service           # expect: success
```

A successful backup starts the off-site copy (`OnSuccess=`). Wait until it is no
longer `activating`, then check the result:

```bash
systemctl is-active aca-gx10-backup-offsite.service   # wait for: inactive
systemctl show -p Result --value aca-gx10-backup-offsite.service   # expect: success
```

Don't continue without both results. This backup is the only way back if a
migration goes wrong.

## 3. Pull and sync the host venv

```bash
sudo git -C /opt/aca pull --ff-only
git -C /opt/aca log --oneline -1                     # the commit you meant to deploy
cd /opt/aca && sudo -H uv sync --frozen
```

## 4. Build and pin the app image

```bash
sudo make -C /opt/aca/deploy/gx10 image
```

The image is built from the checked-out commit, so `make image` refuses a dirty
tree. It pushes `ghcr.io/jankneumann/agentic-content-analyzer:gx10-<sha>` and
prints one line:

```
GX10_APP_IMAGE=ghcr.io/jankneumann/agentic-content-analyzer:gx10-<sha>@sha256:<digest>
```

If the push fails with an authentication error, run `sudo podman login ghcr.io`
and repeat. Replace the `GX10_APP_IMAGE=` line in `/etc/aca/gx10-images.env`
with the printed one (the file stays root-owned, mode `0600`), then run the
provenance gate:

```bash
sudo make -C /opt/aca/deploy/gx10 image-pins
```

## 5. Install units

```bash
sudo make -C /opt/aca/deploy/gx10 install
```

This copies the units, timers and tmpfiles, runs `systemd-analyze verify`,
reloads systemd and enables every unit that has an `[Install]` section, new ones
included.

## 6. Restart

```bash
sudo systemctl restart aca-gx10-secrets.service aca-gx10.service
```

Restarting `aca-gx10-secrets.service` re-renders the runtime env files from
OpenBao. Restarting `aca-gx10.service` then does three things:
1. It removes every container except OpenBao.
2. It brings up the infrastructure and runs `alembic upgrade head` from a
   throwaway `api` container.
3. Only then does it start `api`, `worker`, `scheduler` and `maintenance`.

The workers refuse to start on a stale schema, which is why the migration
comes first.

If the restart leaves units in a `failed` state, recover with the full start
target. It resets the failed units, restarts OpenBao, re-renders secrets and
starts the runtime:

```bash
sudo make -C /opt/aca/deploy/gx10 start
```

## 7. Verify

```bash
sudo make -C /opt/aca/deploy/gx10 status                 # every unit active, every container healthy
sudo make -C /opt/aca/deploy/gx10 logs SINCE="-15min"    # expect no output

for role in api worker scheduler maintenance; do
  sudo podman exec aca-gx10_${role}_1 gx10-role-ready --role "$role"
done

# The schema is at the image's head
sudo podman exec aca-gx10_api_1 alembic current
sudo podman exec aca-gx10_api_1 alembic heads

# The API's telemetry survived startup (fixed in 3aa13372; expect 0)
sudo podman logs --since 15m aca-gx10_api_1 2>&1 | grep -c "Telemetry shut down"
```

Then open Langfuse and confirm new traces arrive after a request. For a deeper
check, run the smoke verifier in
[gx10-observability.md](gx10-observability.md#deterministic-smoke-verifier).

## Rollback

First compare `alembic current` with
`/var/lib/aca/gx10/rollback/alembic-current`.

**The schema did not change.** Go back to the previous commit and image:

```bash
sudo git -C /opt/aca switch --detach "$(sudo cat /var/lib/aca/gx10/rollback/revision)"
cd /opt/aca && sudo -H uv sync --frozen
sudo install -m 0600 -o root -g root /var/lib/aca/gx10/rollback/gx10-images.env /etc/aca/gx10-images.env
sudo make -C /opt/aca/deploy/gx10 image-pins
sudo make -C /opt/aca/deploy/gx10 install
sudo systemctl restart aca-gx10-secrets.service aca-gx10.service
```

Once a fix lands, `sudo git -C /opt/aca switch main` and update normally.

**Migrations ran.** Migrations only move forward, and the previous image is not
guaranteed to work against the newer schema. Prefer fixing forward. If you must
go back, restore Postgres from the step-2 backup using
[BACKUP_RESTORE.md](../BACKUP_RESTORE.md), then roll back as above.

## Known gaps

- **`release_revision` is stuck at the first-install commit.** Its value is read
  from `secret/newsletter/gx10/runtime`, which only first install writes. As a
  result:
  - OTel `service.version`, Langfuse traces and operation attempt rows all report
    that stale commit after every update;
  - nothing in the repo updates it yet;
  - to tell releases apart, use the image tag (`gx10-<sha>`).
- **Reboots are not yet proven.** The host has not survived a real reboot since
  the 2026-10-20 fixes (handoff task 0).

## One-time steps for the update from `dbe14da8`

`/opt/aca` was last deployed at `dbe14da8` on the feature branch. Going to
current `main` (98 commits) needs these extra steps, in this order around the
routine ones.

**Before step 3.** `/opt/aca` was cloned single-branch, so `git pull` never sees
`main`. Switch once (the tree must be clean):

```bash
sudo git -C /opt/aca remote set-branches --add origin main
sudo git -C /opt/aca fetch origin
sudo git -C /opt/aca switch --track origin/main
```

**Between steps 3 and 6, seed the provider keys.** The pulled
`render-secrets.sh` refuses to render until `secret/newsletter/gx10/providers`
exists, so restarting before you seed stops the stack. Seed the keys rotated
after the Railway incident, not the old values:

```bash
sudo /opt/aca/deploy/gx10/openbao/seed-providers-secret.sh   # hidden prompts
```

At least one of `anthropic_api_key`, `openai_api_key` or `gemini_api_key` is
required. The script also re-uploads the `aca-gx10` OpenBao policy, which this
update changes. Field list and rotation:
[handoff task 10](../GX10_HANDOFF.md#10-seed-the-provider-keys--required-before-the-next-restart).

**Step 4 is mandatory.** The renderer now writes `GEMINI_API_KEY`, which images
built before `4f2e9fc0` do not read.

**Step 5 adds a timer.** `aca-gx10-backup-freshness.timer` (hourly) is new and is
enabled by `make install`.

**Step 6 runs four migrations:**
- `d8e2a4c6f1b3` adds the x_bookmarks content source;
- `e4b7c1a9d2f6` adds `source_overrides.managed_by`;
- `f5c8d2b0e3a7` adds the content-reference expansion state;
- `7b80d3af5afa` merges the two heads.

All four are additive.

**Step 7 checks a new fix.** Before `3aa13372`, the startup notification
cleanup shut down the API's telemetry right after every start. The `grep -c`
check in step 7 confirms the fix is live.
