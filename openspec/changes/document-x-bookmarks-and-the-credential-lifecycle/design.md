# Design: Document X bookmarks and the credential lifecycle

## Decisions

- **Document only what the code does.** Every command, flag, default and code
  was read from `--help` output, `src/config/settings.py`,
  `src/ingestion/x_bookmarks.py`, `src/ingestion/credential_failures.py` and
  `src/contracts/workflow_alert_models.py`. `aca ingest substack-sync` has no
  CLI entry point any more (`sync_substack_sources()` has no caller), so its
  examples are removed rather than re-documented.
- **One home per topic, links elsewhere.** The user workflow lives in
  `USER_GUIDE.md`; install/sink/OpenBao/env details in `SETUP.md`; the sync
  endpoint in `TAILNET.md` (already written by ri-14/ri-15); OpenBao roles in
  `OPENBAO.md` (ri-03). New text links to those anchors instead of copying.
- **Capability for the spec delta:** `developer-workflow`, as the brief
  suggested; the requirement is a documentation obligation, not runtime
  behaviour of any capability.
- **CLAUDE.md Critical Gotchas:** only the two pitfalls that destroy data or
  break CI repeatedly (KV v2 clobbering, the ruff pin) are promoted; the rest
  stay in `docs/GOTCHAS.md`.

## Non-goals

- Editing `extension/README.md`, `docs/TAILNET.md` or `docs/OPENBAO.md`, which
  earlier items already updated.
- Restoring a Substack subscription-sync command.
