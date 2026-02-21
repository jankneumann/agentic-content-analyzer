# Skill Design: neon-branch

> **Note:** This is a design reference for the `neon-branch` skill to be implemented
> in the `agentic-coding-tools` repo. It documents the skill contract that the
> `aca neon` CLI commands in this repo are designed to support.

---
name: neon-branch
description: Manage Neon database branches for isolated agent development. Use when starting feature work (create branch), validating changes (test on branch), or cleaning up (delete branch). Designed to be invoked by other skills during their phases.
license: MIT
compatibility: Requires NEON_API_KEY and NEON_PROJECT_ID in environment or .secrets.yaml.
metadata:
  author: project
  version: "1.0"
---

Manage Neon database branches to give each agent session or feature an isolated copy-on-write database.

**Input**: An action — `create`, `verify`, `cleanup`, `list`, or `clean`. Optionally a branch name or change name.

**Prerequisite Check**

Before any action, verify Neon credentials are available:
```bash
aca neon list --json 2>&1 | head -5
```

If this fails with "NEON_API_KEY and NEON_PROJECT_ID are required":
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
   aca neon list --json
   ```
   Parse JSON and check if a branch with this name exists. If it does:
   - Show existing branch info
   - Ask: "Branch already exists. Use existing branch, or recreate?"
   - If recreate: delete first, then create

3. **Create the branch**
   ```bash
   aca neon create "<branch-name>" --json
   ```

4. **Run migrations on the branch**
   ```bash
   DATABASE_URL="<connection_string>" alembic upgrade head
   ```
   This ensures the branch schema is current (production data + latest migrations).

5. **Output the result**
   ```
   ## Neon Branch Ready

   **Branch:** claude/<change-name>
   **Connection:** <connection_string>

   To use this branch:
     export DATABASE_URL="<connection_string>"

   This branch is an isolated copy of production data.
   Changes here do not affect the main database.
   ```

---

### `verify` — Run tests against a branch

Used during validation to smoke-test changes on real data.

**Input**: A branch name or change name.

**Steps**:

1. **Resolve the branch name** (same logic as create)

2. **Get connection string**
   ```bash
   aca neon connection "<branch-name>"
   ```
   If branch doesn't exist, suggest creating it first.

3. **Run the test suite against the branch**
   ```bash
   DATABASE_URL="<connection_string>" pytest tests/ -x -v --timeout=60
   ```

4. **If E2E tests are relevant, run Playwright smoke tests**
   ```bash
   DATABASE_URL="<connection_string>" cd web && pnpm test:e2e:smoke
   ```
   Only run this if the change touches API routes or frontend components.

5. **Report results**
   ```
   ## Branch Verification: claude/<change-name>

   **Unit/Integration tests:** X passed, Y failed
   **E2E smoke tests:** (if run) X passed, Y failed

   ### Failures (if any)
   - test_name: error description
   ```

---

### `cleanup` — Delete a branch

Used after archiving a change to remove the ephemeral branch.

**Input**: A branch name or change name.

**Steps**:

1. **Resolve the branch name**

2. **Check if branch exists**
   ```bash
   aca neon list --json
   ```
   If branch doesn't exist, report "No branch to clean up" and stop.

3. **Delete the branch**
   ```bash
   aca neon delete "<branch-name>" --force
   ```

4. **Confirm deletion**
   ```
   Cleaned up branch: claude/<change-name>
   ```

---

### `list` — Show all branches

**Steps**:
```bash
aca neon list
```

Show the output directly. Highlight branches with `claude/` prefix as agent-managed.

---

### `clean` — Remove stale agent branches

Used for periodic housekeeping.

**Steps**:
```bash
aca neon clean --prefix "claude/" --older-than 24
```

Show what would be deleted and confirm before proceeding.
For non-interactive use (CI):
```bash
aca neon clean --prefix "claude/" --older-than 24 --force
```

---

## Integration with OpenSpec Skills

This skill is designed to be called by other skills at specific lifecycle points:

| OpenSpec Phase | Neon Action | Trigger |
|---------------|-------------|---------|
| `/opsx:apply` (start implementation) | `create` | Before first task |
| `/opsx:verify` (validate change) | `verify` | During verification |
| `/opsx:archive` (finalize change) | `cleanup` | After archiving |

When invoked from another skill, the change name is passed through.
The calling skill should mention: "Creating isolated database branch for this change..."

**Example flow in `/opsx:apply`**:
```
1. Select change: "add-search-rerank"
2. → neon-branch create claude/add-search-rerank
3. Implement tasks using DATABASE_URL from branch
4. → neon-branch verify claude/add-search-rerank
5. Archive change
6. → neon-branch cleanup claude/add-search-rerank
```

---

## Guardrails

- Branch names MUST start with `claude/` — this prefix is used by `clean` to identify agent-managed branches
- Never delete branches that don't start with `claude/` (especially `main`)
- Always check if branch exists before creating (avoid duplicates)
- Always run `alembic upgrade head` after creating a branch (schema may have new migrations)
- If Neon credentials are missing, fail gracefully — don't block the calling skill
- Connection strings contain credentials — never log them in full, only show in direct output to user
- The `clean` command with `--force` should only be used in CI, never interactively without confirmation
