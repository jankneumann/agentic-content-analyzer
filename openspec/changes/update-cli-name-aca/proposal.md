# Change: Rename CLI tool to aca

## Why
The CLI binary should match the new product name and avoid confusion with existing tooling.

## What Changes
- Update the CLI command name from `newsletter-cli` to `aca` in user-facing docs and specs.
- Keep subcommand structure and behavior identical.

## Impact
- Affected specs: `specs/profile-configuration/spec.md`
- Affected code: `src/cli/main.py`, `src/cli/profile_commands.py`
- Affected docs: `CLAUDE.md`, `docs/SETUP.md`, `docs/PROFILES.md`
