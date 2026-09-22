# Document X bookmarks and the credential lifecycle

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `document-x-bookmarks-and-the-credential-lifecycle`
> Effort: M
> Priority: 7

## Summary

Update docs/USER_GUIDE.md, docs/SETUP.md, docs/MOBILE_CAPTURE.md, CLAUDE.md, and docs/GOTCHAS.md so the X bookmarks source, the session capture command, the sync button, and the credential lifecycle are discoverable, including the two new gotchas.

## Dependencies

- `ri-06`
- `ri-08`
- `ri-12`
- `ri-13`

## Acceptance Outcomes

- Every new CLI command and setting appears in the CLAUDE.md documentation index tables and docs/SETUP.md.
- docs/MOBILE_CAPTURE.md states that bookmarking on X replaces the share-sheet path for X content.
- docs/GOTCHAS.md contains entries for frozen settings versus the live provider and for KV v2 create_or_update clobbering sibling keys.

## Rationale

The new commands and settings must appear in the documentation index and setup guide or the operator will fall back to the manual DevTools path the proposal removes.
