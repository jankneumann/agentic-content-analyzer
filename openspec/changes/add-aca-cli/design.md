# Design: Add aca CLI

## Decision 1: CLI Framework

**Choice**: Typer (already used for `newsletter-cli profile` commands)

**Alternatives considered**:
- **Click**: Lower-level, more boilerplate. Typer wraps Click with type annotations.
- **argparse**: Standard library, but verbose and no Rich integration.

**Rationale**: Typer is already a project dependency, provides automatic `--help` generation, Rich integration, and type-safe command definitions. Staying with Typer avoids adding dependencies and keeps the CLI consistent.

## Decision 2: Async Service Adapter Pattern

**Choice**: Thin sync wrappers using `asyncio.run()` in `src/cli/adapters.py`

**Alternatives considered**:
- **Make all services sync**: Would require rewriting services that use `await` (digest creation, podcast generation, review). Too invasive.
- **Use `anyio.from_thread.run`**: More complex, no benefit for a CLI context.
- **Use `click-async`/`asyncclick`**: Adds dependency and Typer compatibility is uncertain.

**Rationale**: `asyncio.run()` is the simplest approach for CLI commands that need to call async services. Each CLI command that wraps an async service calls `asyncio.run(service_method(...))`. This is safe because CLI commands are the top-level entry point — there's no existing event loop to conflict with.

**Example**:
```python
# src/cli/adapters.py
import asyncio
from src.processors.digest_creator import DigestCreator

def create_digest_sync(request):
    creator = DigestCreator()
    return asyncio.run(creator.create_digest(request))
```

## Decision 3: Command Module Organization

**Choice**: One file per command group (e.g., `ingest_commands.py`, `digest_commands.py`)

**Alternatives considered**:
- **Single file**: Would become too large (500+ lines).
- **One file per subcommand**: Too granular (20+ files), harder to navigate.
- **Nested packages**: Overkill for the number of commands.

**Rationale**: Each command group maps to one Typer sub-app in its own file. The root `app.py` imports and mounts them. This keeps files focused (50–150 lines each) and enables parallel implementation — each file can be developed by a separate agent without merge conflicts.

**File layout**:
```
src/cli/
├── app.py                  # Root Typer app, mounts sub-apps
├── adapters.py             # Sync wrappers for async services
├── ingest_commands.py      # aca ingest (gmail, rss, youtube, podcast, files)
├── summarize_commands.py   # aca summarize (pending, id, list)
├── digest_commands.py      # aca create-digest (daily, weekly)
├── pipeline_commands.py    # aca pipeline (daily, weekly)
├── review_commands.py      # aca review (list, view, revise)
├── analyze_commands.py     # aca analyze (themes)
├── graph_commands.py       # aca graph (extract-entities, query)
├── podcast_commands.py     # aca podcast (generate, list-scripts)
├── manage_commands.py      # aca manage (setup-gmail, verify-setup, ...)
├── profile_commands.py     # aca profile (existing, renamed)
├── main.py                 # Legacy newsletter-cli entrypoint (deprecated alias)
└── __main__.py             # python -m src.cli support
```

## Decision 4: Interactive Revision REPL

**Choice**: Simple `input()` loop with Rich display

**Alternatives considered**:
- **prompt_toolkit**: Full readline-like experience with history. Adds dependency.
- **Click.prompt**: Less control over display.
- **Non-interactive mode only**: Would lose the multi-turn revision capability.

**Rationale**: Start with a simple `input()` REPL that shows the digest, accepts revision instructions, calls `ReviewService.process_revision_turn()`, and displays the updated version. Users exit by typing "done" or Ctrl-D (EOFError). This can be upgraded to `prompt_toolkit` later if needed. The review service already handles multi-turn conversation state.

## Decision 5: Backward Compatibility Strategy

**Choice**: Deprecation warnings + functional shims for 1-2 release cycles

**Approach**:
1. Register both `aca` and `newsletter-cli` in pyproject.toml console_scripts
2. `newsletter-cli` app emits `DeprecationWarning` on every invocation, then delegates to the same Typer app
3. Legacy `python -m src.ingestion.*` modules emit warnings and call the corresponding service directly (no CLI delegation to avoid subprocess overhead)
4. Document migration in CLAUDE.md: "Use `aca` instead of `newsletter-cli` or `python -m src.*`"

## Decision 6: Output Format

**Choice**: Rich by default, `--json` flag for machine-readable output

**Rationale**: Rich is already a dependency (used in profile commands). Human-readable output uses Rich tables and panels. The `--json` flag outputs valid JSON to stdout and sends progress/status to stderr, enabling piping and scripting.

## Risks

| Risk | Mitigation |
|------|------------|
| `asyncio.run()` conflicts if called from async context | CLI is always the top-level entry; document that `aca` must not be called from within an event loop |
| Large number of commands makes help output overwhelming | Use Typer sub-apps to group commands; each group has focused `--help` |
| Service API changes break CLI | CLI tests mock services; CI runs both API and CLI test suites |
