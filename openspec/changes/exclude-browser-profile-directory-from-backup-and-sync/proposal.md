# Exclude browser profile directory from backup and sync

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `exclude-browser-profile-directory-from-backup-and-sync`
> Effort: S
> Priority: 6

## Summary

Add ~/.aca/browser-profiles/ to the exclusion lists of aca backup, aca sync, and every artifacts tarball, and document the exclusion in the backup and sync docs.

## Dependencies

- None

## Acceptance Outcomes

- A test proves aca backup run, aca sync, and the artifacts tarball builder each skip a populated ~/.aca/browser-profiles/ directory.
- docs/BACKUP_RESTORE.md lists ~/.aca/browser-profiles/ as an excluded path.

## Rationale

The persistent Playwright profile is a session credential; it must never be captured off-site or copied between machines.
