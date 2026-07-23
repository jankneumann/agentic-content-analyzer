
## Key Documentation

Before making significant changes, review the relevant documentation:

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](CLAUDE.md) | Primary agent instructions, quick reference, gotchas |
| [Setup Guide](docs/SETUP.md) | Environment setup, database/storage providers, configuration |
| [Architecture](docs/ARCHITECTURE.md) | System design, tech stack, data flows |
| [Development Guide](docs/DEVELOPMENT.md) | Commands, patterns, testing best practices |
| [Markdown Pipeline](docs/MARKDOWN_PIPELINE_DESIGN.md) | End-to-end markdown flow from ingestion to rendering |
| [Case Studies](docs/CASE_STUDIES.md) | Refactoring lessons, migration patterns, design decisions |
| [OpenSpec Schemas](openspec/schemas/) | Stable local reference for OpenSpec workflow schemas and templates |

### Quick Reference by Task

| Task | Start Here |
|------|-----------|
| Database/storage setup | [CLAUDE.md#database-providers](CLAUDE.md#database-providers), [CLAUDE.md#image-storage-providers](CLAUDE.md#image-storage-providers) |
| Adding new features | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Writing tests | [docs/DEVELOPMENT.md#testing](docs/DEVELOPMENT.md#testing) |
| Debugging issues | [CLAUDE.md#critical-gotchas](CLAUDE.md#critical-gotchas) |

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Issue Tracking

Use GitHub Issues for follow-up work. Before ending a session, create issues for
unfinished work and close or update issues completed during the session.

## OpenSpec Schema Reference

Keep `openspec/schemas/` tracked as the stable local reference for OpenSpec
workflow schemas and templates. Do not treat this directory as disposable
generated output or remove it during cleanup.
