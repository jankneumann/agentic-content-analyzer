# Design: Exclude browser profile directory from backup and sync

## Decisions

### D1: Two independent checks, not one
- **Resolved configured root** (`browser_profiles_dir`, `excluded_roots()`). This
  covers an operator who moves the profiles somewhere with an unrecognisable name.
- **Component pattern** (`.aca/browser-profiles`). This covers what the setting
  cannot: `~` expands per user, and `aca-backup.service` runs as `aca-backup`, so
  the backup resolves a different home than the operator who logged in.

### D2: Exclude inside `tar`, not by enumerating files in Python
The executor streams bytes host-side and forbids shell pipelines. `tar
--exclude` keeps the stream wholesale, so orphaned artifacts are still captured,
and adds no interpreter I/O. The exact exclusion is spelled as tar names members:
the operand as given plus the path relative to its resolved form. It is anchored,
with wildcards off, so `sessions` never excludes `sessions-archive`. Tests execute
the real argv and inspect the member list, so a wrong spelling fails a test
instead of silently shipping cookies.

### D3: Fail closed on containment
The check compares resolved paths. If an artifact directory contains the profiles
root, the exclusion is added. If the directory is inside the profiles root, it is
dropped. If none remain, the store is the existing named skip
`no_artifact_directories_present`.

### D4: File sync checks both sides
The source side stops a live session being copied out. The target side stops a
sync overwriting a session on the receiving machine. Non-local providers only get
the pattern check, because a bucket key cannot resolve into the local profile root.

## Non-goals
- No change to the systemd unit. `ProtectHome=tmpfs` was considered and rejected,
  because an operator with artifact paths under `/home` would lose those artifacts
  from the backup silently.
- `artifact_directories` still ignores `storage_local_paths`. That is a
  pre-existing gap and out of scope.
