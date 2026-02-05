# Tasks: Add aca CLI

## 1. Specification Updates (independent — can run in parallel with each other)
- [ ] 1.1 Create new `specs/cli-interface/spec.md` defining `aca` commands, workflows, error handling, and output format
- [ ] 1.2 Update `specs/profile-configuration/spec.md` to rename `newsletter-cli profile` → `aca profile` and add backward-compatibility deprecation note

## 2. CLI Architecture (sequential chain: 2.1 → 2.2 → 2.3)
- [ ] 2.1 Register `aca` and `newsletter-cli` console_scripts entrypoints in `pyproject.toml`. Create `src/cli/app.py` with root Typer app that pre-wires all sub-app imports and `add_typer()` calls for: ingest, summarize, create-digest, pipeline, review, analyze, graph, podcast, manage, profile. Each sub-app file starts as a stub module exporting a `typer.Typer()` instance so imports resolve immediately.
  - **File scope**: `pyproject.toml`, `src/cli/app.py`, `src/cli/__init__.py`, stub `*_commands.py` files (empty Typer apps only)
  - **Depends on**: nothing (can start immediately)
  - **Note**: Task 2.1 creates ALL `*_commands.py` files as stubs. Tasks 3.1–3.10 then only modify their own `*_commands.py` file — they do NOT modify `app.py`. This eliminates file overlap between parallel tasks.
- [ ] 2.2 Create sync adapter module `src/cli/adapters.py` with wrapper functions that run async service methods via `asyncio.run()`. Async services needing adapters: `DigestCreator.create_digest()`, `PodcastScriptGenerator.generate_script()`, `ReviewService.list_pending_reviews()`, `ReviewService.start_revision_session()`, `ReviewService.process_revision_turn()`, `ReviewService.apply_revision()`, `ReviewService.finalize_review()`, `ThemeAnalyzer` methods. Sync services (no adapter needed): all ingestion services, `ContentSummarizer`.
  - **File scope**: `src/cli/adapters.py`
  - **Depends on**: 2.1 (needs app structure)
- [ ] 2.3 Add deprecation shims: update legacy `__main__.py` modules in `src/ingestion/` and `src/processors/` to emit `DeprecationWarning` and delegate to `aca` commands; keep `newsletter-cli` as alias entrypoint
  - **File scope**: `src/ingestion/*/__main__.py`, `src/processors/*/__main__.py`, `pyproject.toml`
  - **Depends on**: 2.1, all 3.x tasks (needs commands to exist before delegating)

## 3. Command Implementations (each creates its own file — parallelizable after 2.1 + 2.2)
- [ ] 3.1 Implement `src/cli/ingest_commands.py`: gmail, rss, youtube, podcast, files subcommands
  - **File scope**: `src/cli/ingest_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.2 Implement `src/cli/summarize_commands.py`: pending, id, list subcommands
  - **File scope**: `src/cli/summarize_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.3 Implement `src/cli/digest_commands.py`: daily, weekly subcommands
  - **File scope**: `src/cli/digest_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.4 Implement `src/cli/pipeline_commands.py`: daily, weekly subcommands
  - **File scope**: `src/cli/pipeline_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.5 Implement `src/cli/review_commands.py`: list, view, revise subcommands (revise uses a simple `input()` REPL loop per design.md Decision 4)
  - **File scope**: `src/cli/review_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.6 Implement `src/cli/analyze_commands.py`: themes subcommand
  - **File scope**: `src/cli/analyze_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.7 Implement `src/cli/graph_commands.py`: extract-entities, query subcommands
  - **File scope**: `src/cli/graph_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.8 Implement `src/cli/podcast_commands.py`: generate, list-scripts subcommands
  - **File scope**: `src/cli/podcast_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.9 Implement `src/cli/manage_commands.py`: setup-gmail, verify-setup, railway-sync, check-profile-secrets subcommands
  - **File scope**: `src/cli/manage_commands.py`
  - **Depends on**: 2.1, 2.2
- [ ] 3.10 Rename existing `src/cli/profile_commands.py` to use `aca profile` command naming; update imports in app.py
  - **File scope**: `src/cli/profile_commands.py`, `src/cli/app.py`
  - **Depends on**: 2.1

## 4. Documentation (depends on all 3.x tasks)
- [ ] 4.1 Update CLI references in `CLAUDE.md`
  - **File scope**: `CLAUDE.md`
  - **Depends on**: 3.1–3.10
- [ ] 4.2 Update CLI references in `docs/SETUP.md`
  - **File scope**: `docs/SETUP.md`
  - **Depends on**: 3.1–3.10
- [ ] 4.3 Update CLI references in `docs/PROFILES.md`
  - **File scope**: `docs/PROFILES.md`
  - **Depends on**: 3.1–3.10

## 5. Validation (depends on 3.x and 4.x)
- [ ] 5.1 Add CLI unit tests using Typer CliRunner with mocked services for each command group: one test file per command module (e.g., `tests/cli/test_ingest_commands.py`)
  - **File scope**: `tests/cli/`
  - **Depends on**: 3.1–3.10
- [ ] 5.2 Run `pytest`, `ruff`, and `mypy` checks across `src/cli/` and `tests/cli/`
  - **Depends on**: 5.1

## Dependency Graph Summary

```
Independent: 1.1, 1.2 (spec work, no code dependencies)
Sequential:  2.1 → 2.2 → [3.1–3.10 in parallel] → 2.3 → [4.1–4.3 in parallel] → 5.1 → 5.2
Max parallel width: 10 (tasks 3.1–3.10 after 2.1+2.2 complete)
File overlap: None between 3.x tasks (each owns only its *_commands.py file; app.py is pre-wired in 2.1)
```
