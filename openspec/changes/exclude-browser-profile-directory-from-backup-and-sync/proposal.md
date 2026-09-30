# Exclude browser profile directory from backup and sync

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-07`)
> Change ID: `exclude-browser-profile-directory-from-backup-and-sync`

## Why

`aca auth session substack|x` (ri-08) will keep a Playwright persistent browser
profile per site under `~/.aca/browser-profiles/<site>/`. That directory holds live
session cookies. It is a credential, and it must never be captured off-site by
`aca backup run` or copied between machines by `aca sync`.

Today nothing references it, but two copy paths could reach it:

- **Artifacts tarball** (`src/services/backup/stores.py`): `tar` over the
  `image_storage_path`, `podcast_storage_path` and `audio_digest_storage_path`
  directories. When an operator points one of these at `$HOME` or `~/.aca`, the
  profile directory lands in `artifacts.tar`.
- **File sync** (`src/sync/file_syncer.py`, `aca sync push`): copies whatever path
  a database row names, resolved under a local bucket root. The traversal guard
  keeps paths inside the root. It cannot help when the root itself contains the
  profile directory.

The other paths (`pg_dump`, graph dumps, the OpenBao raft snapshot, `aca sync
export/import`, `aca manage restore-from-cloud`) copy no local files.

## What Changes

- New `src/config/browser_profiles.py` is the single place the capture command and
  every copy path agree on. It provides `DEFAULT_BROWSER_PROFILES_DIR`,
  `browser_profiles_dir()`, the `excluded_roots()` denylist hook,
  `EXCLUDED_PATH_PATTERNS` (`.aca/browser-profiles`) and the matching helpers.
- New setting `browser_profiles_dir` (env `BROWSER_PROFILES_DIR`), default
  `~/.aca/browser-profiles`.
- Artifacts `tar` argv gains `--no-wildcards --no-anchored
  --exclude=.aca/browser-profiles`. For each artifact directory that CONTAINS the
  resolved configured root, it also gains `--anchored --exclude=<operand>/<rel>`,
  all before the operands. An artifact directory that IS or sits inside the
  profiles root is dropped. The argv is still built without a shell.
- `FileSyncer` drops every ref that matches the pattern or whose resolved local
  path, on the source or the target side, falls inside an excluded root. It does
  this before the dry run or the copy, and counts the drops in the new
  `FileSyncStats.excluded`.
- Docs: `docs/BACKUP_RESTORE.md` gains an "Excluded paths" section. There are also
  short notes in `docs/USER_GUIDE.md` (the `aca sync` section) and `docs/SYNC_DOWN.md`.

## Impact

- Specs: `backup-and-restore`, `database-sync` (ADDED requirements only).
- Code: `src/config/browser_profiles.py` (new), `src/config/settings.py`,
  `src/services/backup/stores.py`, `src/sync/file_syncer.py`.
- Tests: `tests/test_services/test_browser_profile_exclusion.py`. They run the real
  `tar` argv and list the archive members, drive `BackupEngine.run()`, and run
  `FileSyncer` against real `LocalFileStorage` roots.
- No migration, no contract change, no new dependency. GNU tar is required for
  `--anchored`/`--no-wildcards`, and the gx-10 host already has it. BSD tar would
  fail the artifacts store loudly rather than silently include the profile.
