---
allowed-tools: Bash(git status:*), Bash(git add:*), Bash(git pull:*), Bash(git push:*), Bash(git commit:*), Bash(gh pr create:*), Bash(gh pr merge:*), Bash(pytest:*), Bash(mypy:*)
description: Complete feature with tests, commit, PR, and documentation
---

# Finalize Feature

## 1. Verify Quality
- Run `pytest` to ensure all tests pass
- Run `mypy src/` to check for type errors
- Fix any failures before proceeding

## 2. Commit Changes
- Run `git status` to review all changes
- Stage relevant files with `git add`
- Create descriptive commit message explaining the "why"
- Follow commit message format in @CLAUDE.md

## 3. Push and Create PR
- Pull latest from main: `git pull --rebase origin main`
- Push branch to remote: `git push origin <branch-name>`
- Create PR with `gh pr create` including:
  - Clear title summarizing the feature
  - Summary section with bullet points
  - Test plan section
- Merge PR with `gh pr merge`

## 4. Update Documentation
- Add lessons learned to @CLAUDE.md (patterns, gotchas, best practices discovered)
- Move implementation plan from `.claude/plans/` to `docs/plans/` if applicable
- Update relevant docs if feature changes documented behavior

## 5. Cleanup
- Clear todo list after completion
- Delete local feature branch if desired
