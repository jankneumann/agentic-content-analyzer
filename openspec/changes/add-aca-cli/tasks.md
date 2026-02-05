## 1. Specification Updates
- [ ] 1.1 Add new CLI interface spec defining `aca` commands and workflows
- [ ] 1.2 Update profile-configuration spec to reference `aca profile`

## 2. CLI Architecture
- [ ] 2.1 Create shared workflow service functions for CLI and API
- [ ] 2.2 Implement `aca` Typer entrypoint with subcommand groups
- [ ] 2.3 Add backward-compatible shims for legacy script entrypoints

## 3. Command Implementations
- [ ] 3.1 Ingest subcommands (gmail, rss, youtube, podcast, files)
- [ ] 3.2 Summarize subcommands (pending, id, list)
- [ ] 3.3 Create-digest subcommands (daily, weekly)
- [ ] 3.4 Pipeline subcommands (daily, weekly)
- [ ] 3.5 Review/Revise subcommands (list, view, revise)
- [ ] 3.6 Analyze subcommands (themes)
- [ ] 3.7 Graph subcommands (extract-entities, query)
- [ ] 3.8 Podcast subcommands (generate, list-scripts)
- [ ] 3.9 Manage subcommands (setup-gmail, verify-setup, railway-sync, check-profile-secrets)

## 4. Documentation
- [ ] 4.1 Update CLI references in CLAUDE.md
- [ ] 4.2 Update CLI references in docs/SETUP.md
- [ ] 4.3 Update CLI references in docs/PROFILES.md

## 5. Validation
- [ ] 5.1 Add CLI tests for new command groups
- [ ] 5.2 Run relevant tests/lint checks
