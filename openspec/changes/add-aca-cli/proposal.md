# Change: Add aca CLI with workflow subcommands

## Why
Current CLI coverage is fragmented across scripts. A unified `aca` command with workflow-oriented subcommands will improve usability and keep CLI and API behavior aligned.

## What Changes
- Add a top-level `aca` CLI with subcommands for ingest, summarize, create-digest, pipeline, review/revise, analyze, graph, podcast, and manage.
- Define shared input models and adapters so CLI and API call the same workflow services.
- Deprecate direct script entrypoints in favor of `aca` while keeping backward-compatible fallbacks.

## Impact
- Affected specs: `specs/cli-interface/spec.md`, `specs/profile-configuration/spec.md` (command name alignment)
- Affected code: `src/cli/*`, workflow services, and script entrypoints
- Affected docs: CLI references in `CLAUDE.md`, `docs/SETUP.md`, `docs/PROFILES.md`
