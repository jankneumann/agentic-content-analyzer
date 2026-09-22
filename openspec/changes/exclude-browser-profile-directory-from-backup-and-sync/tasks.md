# Tasks: Exclude browser profile directory from backup and sync

> Change ID: `exclude-browser-profile-directory-from-backup-and-sync`

## 1. Shared definition
- [x] 1.1 Add `src/config/browser_profiles.py` (default dir, `browser_profiles_dir()`, `excluded_roots()` denylist hook, `EXCLUDED_PATH_PATTERNS`, `matches_excluded_pattern`, `is_excluded_path`, `excluded_subpaths`)
- [x] 1.2 Add `browser_profiles_dir` setting (env `BROWSER_PROFILES_DIR`) defaulting to `~/.aca/browser-profiles`

## 2. Backup
- [x] 2.1 Artifacts tar argv: pattern exclusion plus anchored exclusion of each contained configured root, before operands, no shell
- [x] 2.2 Drop artifact directories that are inside the profiles root
- [x] 2.3 Tests: execute the real tar argv and assert no profile member; drive `BackupEngine.run()` end to end

## 3. Sync
- [x] 3.1 `FileSyncer` drops refs into excluded roots (source and target) or matching the pattern, before dry run and copy; `FileSyncStats.excluded`
- [x] 3.2 Tests: source rooted at a home containing a populated profile; unrecognisable configured root; target-side protection; dry run; non-local providers

## 4. Docs and validation
- [x] 4.1 `docs/BACKUP_RESTORE.md` "Excluded paths" lists `~/.aca/browser-profiles/`
- [x] 4.2 Sync notes in `docs/USER_GUIDE.md` and `docs/SYNC_DOWN.md`
- [x] 4.3 ruff, mypy, targeted pytest, `openspec validate --strict`
