# Skill Design: neon-branch

> **Note:** This is a design reference for the `neon-branch` skill to be implemented
> in this repo's `.claude/` directory (project-specific skill) once the generic
> OpenSpec skills from `agentic-coding-tools` have been synced.
>
> The skill uses the official `neonctl` CLI when available for features like
> `--expires-at` (auto-expiring branches) and `schema-diff`. Falls back to
> `aca neon` (this repo's Python CLI) when `neonctl` is not installed.

---
name: neon-branch
description: Manage Neon database branches for isolated agent development. Use when starting feature work (create branch), validating changes (test on branch), or cleaning up (delete branch). Designed to be invoked by other skills during their phases.
license: MIT
compatibility: Requires NEON_API_KEY and NEON_PROJECT_ID in environment or .secrets.yaml. Optionally uses neonctl (npm i -g neonctl) for --expires-at and schema-diff.
metadata:
  author: project
  version: "2.0"
---

Manage Neon database branches to give each agent session or feature an isolated copy-on-write database.

**Input**: An action — `create`, `verify`, `cleanup`, `list`, or `clean`. Optionally a branch name or change name.

## CLI Tool Selection

Two CLIs can manage Neon branches. Prefer `neonctl` when available:

| Feature | `neonctl` (official) | `aca neon` (this repo) |
|---------|---------------------|----------------------|
| Install | `npm i -g neonctl` | Built-in (Python) |
| Branch create | Yes | Yes |
| `--expires-at` (auto-TTL) | Yes | No |
| `schema-diff` | Yes | No |
| Connection string | Yes (`--pooled`) | Yes (`--pooled/--direct`) |
| JSON output | `--output json` | `--json` |
| Stale branch cleanup | Manual or via TTL | `aca neon clean` |
| Python test fixtures | No | Yes (`NeonBranchManager`) |

**Detection**: Check which CLI is available before proceeding:
```bash
# Prefer neonctl if installed
if command -v neonctl &>/dev/null; then
  NEON_CLI="neonctl"
else
  NEON_CLI="aca neon"
fi
```

## Prerequisite Check

Before any action, verify Neon credentials are available:
```bash
# With neonctl
neonctl branches list --project-id "$NEON_PROJECT_ID" --output json 2>&1 | head -5

# Or with aca neon
aca neon list --json 2>&1 | head -5
```

If this fails with authentication errors:
- Tell the user: "Neon branch management requires NEON_API_KEY and NEON_PROJECT_ID. Set them in `.secrets.yaml` or your environment."
- Stop. Do not proceed.

---

## Actions

### `create` — Create a branch for feature work

Used when starting implementation. Creates a copy-on-write branch from production data.

**Input**: A change name (kebab-case) or branch name. If invoked from an OpenSpec change, derive from the change name.

**Steps**:

1. **Derive branch name**
   - If a change name is given: `claude/<change-name>` (e.g., `claude/add-auth`)
   - If invoked from `/opsx:apply`: use the change name from context
   - Branch names must start with `claude/`

2. **Check if branch already exists**
   ```bash
   # neonctl
   neonctl branches list --project-id "$NEON_PROJECT_ID" --output json | grep '"claude/<change-name>"'

   # or aca neon
   aca neon list --json
   ```
   If the branch already exists:
   - Show existing branch info
   - Ask: "Branch already exists. Use existing branch, or recreate?"
   - If recreate: delete first, then create

3. **Create the branch with auto-expiration**
   ```bash
   # neonctl (preferred) — branch auto-deletes after 48 hours
   neonctl branches create \
     --project-id "$NEON_PROJECT_ID" \
     --name "claude/<change-name>" \
     --parent main \
     --expires-at "$(date -u -d '+48 hours' +%Y-%m-%dT%H:%M:%SZ)" \
     --output json

   # aca neon (fallback) — no auto-expiration, needs manual cleanup
   aca neon create "claude/<change-name>" --json
   ```

4. **Get the connection string**
   ```bash
   # neonctl
   neonctl connection-string "claude/<change-name>" --project-id "$NEON_PROJECT_ID" --pooled

   # aca neon
   aca neon connection "claude/<change-name>"
   ```

5. **Run migrations on the branch**
   ```bash
   DATABASE_URL="<connection_string>" alembic upgrade head
   ```
   This ensures the branch schema is current (production data + latest migrations).

6. **Output the result**
   ```
   ## Neon Branch Ready

   **Branch:** claude/<change-name>
   **Expires:** <48h from now> (auto-cleanup via --expires-at)
   **Connection:** <connection_string>

   To use this branch:
     export DATABASE_URL="<connection_string>"

   This branch is an isolated copy of production data.
   Changes here do not affect the main database.
   ```

---

### `verify` — Validate changes on a branch

Used during validation to check schema changes and smoke-test against real data.

**Input**: A branch name or change name.

**Steps**:

1. **Resolve the branch name** (same logic as create)

2. **Run schema diff against main (if neonctl available)**
   ```bash
   neonctl branches schema-diff main "claude/<change-name>" \
     --project-id "$NEON_PROJECT_ID"
   ```
   This shows exactly what schema changes the branch introduced.
   Include the diff output in the verification report.
   If no schema changes: note "No schema differences from main."

3. **Get connection string**
   ```bash
   # neonctl
   neonctl connection-string "claude/<change-name>" --project-id "$NEON_PROJECT_ID" --pooled

   # or aca neon
   aca neon connection "claude/<change-name>"
   ```
   If branch doesn't exist, suggest creating it first.

4. **Run the test suite against the branch**
   ```bash
   DATABASE_URL="<connection_string>" pytest tests/ -x -v --timeout=60
   ```

5. **If E2E tests are relevant, run Playwright smoke tests**
   ```bash
   DATABASE_URL="<connection_string>" cd web && pnpm test:e2e:smoke
   ```
   Only run this if the change touches API routes or frontend components.

6. **Report results**
   ```
   ## Branch Verification: claude/<change-name>

   ### Schema Diff (vs main)
   <schema-diff output or "No schema differences">

   ### Test Results
   **Unit/Integration tests:** X passed, Y failed
   **E2E smoke tests:** (if run) X passed, Y failed

   ### Failures (if any)
   - test_name: error description
   ```

---

### `cleanup` — Delete a branch

Used after archiving a change to remove the ephemeral branch.
If `--expires-at` was used during creation, cleanup may be unnecessary
(the branch will auto-delete). Still good practice to clean up explicitly.

**Input**: A branch name or change name.

**Steps**:

1. **Resolve the branch name**

2. **Check if branch exists**
   ```bash
   # neonctl
   neonctl branches list --project-id "$NEON_PROJECT_ID" --output json

   # or aca neon
   aca neon list --json
   ```
   If branch doesn't exist (already expired or deleted), report "No branch to clean up" and stop.

3. **Delete the branch**
   ```bash
   # neonctl
   neonctl branches delete "claude/<change-name>" --project-id "$NEON_PROJECT_ID"

   # or aca neon
   aca neon delete "claude/<change-name>" --force
   ```

4. **Confirm deletion**
   ```
   Cleaned up branch: claude/<change-name>
   ```

---

### `list` — Show all branches

**Steps**:
```bash
# neonctl (richer output)
neonctl branches list --project-id "$NEON_PROJECT_ID"

# or aca neon
aca neon list
```

Show the output directly. Highlight branches with `claude/` prefix as agent-managed.

---

### `clean` — Remove stale agent branches

Used for periodic housekeeping. Less critical when `--expires-at` is used during
creation, but still useful for branches created without TTL.

**Steps**:
```bash
# aca neon (has built-in prefix/age filtering)
aca neon clean --prefix "claude/" --older-than 24

# For non-interactive use (CI):
aca neon clean --prefix "claude/" --older-than 24 --force
```

Note: `neonctl` doesn't have an equivalent bulk cleanup command — use `aca neon clean`.

---

## Integration with OpenSpec Skills

This skill is designed to be called by other skills at specific lifecycle points:

| OpenSpec Phase | Neon Action | Key Feature Used |
|---------------|-------------|-----------------|
| `/opsx:apply` (start implementation) | `create` | `--expires-at` for auto-cleanup |
| `/opsx:verify` (validate change) | `verify` | `schema-diff` for schema review |
| `/opsx:archive` (finalize change) | `cleanup` | Explicit deletion (if not expired) |

When invoked from another skill, the change name is passed through.
The calling skill should mention: "Creating isolated database branch for this change..."

**Example flow in `/opsx:apply`**:
```
1. Select change: "add-search-rerank"
2. → neon-branch create claude/add-search-rerank  (with --expires-at +48h)
3. Implement tasks using DATABASE_URL from branch
4. → neon-branch verify claude/add-search-rerank  (schema-diff + tests)
5. Archive change
6. → neon-branch cleanup claude/add-search-rerank (explicit delete, or let TTL handle it)
```

---

## Guardrails

- Branch names MUST start with `claude/` — this prefix is used by `clean` to identify agent-managed branches
- Never delete branches that don't start with `claude/` (especially `main`)
- Always check if branch exists before creating (avoid duplicates)
- Always run `alembic upgrade head` after creating a branch (schema may have new migrations)
- If Neon credentials are missing, fail gracefully — don't block the calling skill
- Connection strings contain credentials — never log them in full, only show in direct output to user
- Prefer `--expires-at` over manual cleanup — set 48h TTL for feature branches, 4h for CI branches
- Use `schema-diff` before running tests — catch unintended schema changes early
- The `clean` command with `--force` should only be used in CI, never interactively without confirmation
