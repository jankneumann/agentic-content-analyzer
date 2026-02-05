# Change: Add aca CLI with workflow subcommands

## Why
Current CLI coverage is fragmented across `python -m src.ingestion.*` and `python -m src.processors.*` scripts, with only profile management exposed via the `newsletter-cli` Typer app. A unified `aca` command with workflow-oriented subcommands will:
- Improve developer ergonomics by consolidating all operations under a single entrypoint
- Ensure CLI and API behavior stay aligned by sharing the same workflow service layer
- Enable tab-completion and discoverable help for all capabilities
- Provide a foundation for future automation and scripting

## What Changes
- **New capability spec**: Create `specs/cli-interface/spec.md` defining the `aca` command structure and all subcommands.
- **Modified capability spec**: Update `specs/profile-configuration/spec.md` to rename `newsletter-cli profile` commands to `aca profile`.
- **CLI entrypoint**: Register `aca` as a console_scripts entrypoint in `pyproject.toml` and implement the Typer app with subcommand groups for: ingest, summarize, create-digest, pipeline, review, analyze, graph, podcast, manage, and profile.
- **Shared service adapters**: Create thin sync adapter functions where CLI needs to call async workflow services (e.g., digest creation, podcast generation, review). CLI and API both delegate to the same underlying service classes.
- **Backward compatibility**: Keep `newsletter-cli` as a deprecated alias. Legacy `python -m src.ingestion.*` entrypoints emit deprecation warnings and delegate to the new CLI.
- **Output format**: All commands use Rich console output by default, with a `--json` flag for machine-readable output.

## Impact
- **New spec**: `specs/cli-interface/spec.md` (created by this change)
- **Modified spec**: `specs/profile-configuration/spec.md` (command name `newsletter-cli` → `aca`)
- **Affected code**: `src/cli/` (new command modules), `pyproject.toml` (entrypoint registration), workflow services (sync adapters where needed)
- **Affected docs**: CLI references in `CLAUDE.md`, `docs/SETUP.md`, `docs/PROFILES.md`
