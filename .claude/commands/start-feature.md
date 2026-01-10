---
allowed-tools: Bash(git checkout:*), Bash(git pull:*), Bash(git status:*), Bash(git branch:*), Bash(pytest:*)
argument-hint: <feature-description>
description: Initialize a new feature branch with planning
---

# Start Feature: $ARGUMENTS

## 1. Prepare Environment
- Pull latest changes from main: `git pull origin main`
- Create feature branch with descriptive name based on: $ARGUMENTS
- Branch naming: `feature/<short-description>` or `claude/<short-description>`

## 2. Verify Clean State
- Run `git status` to ensure clean working directory
- Run `pytest` to verify tests pass before starting

## 3. Plan Implementation
- Enter planning mode to design the implementation approach
- Follow guidelines in @CLAUDE.md and @docs/*.md
- Consider architecture patterns documented in @docs/ARCHITECTURE.md
- Store the implementation plan in @docs/plans/ with date prefix (e.g., `2025-01-10-feature-name.md`)

## 4. Test-Driven Development
- Write tests first that define expected behavior
- Implement code to make tests pass
- Don't finish until all tests pass

## 5. Track Progress
- Use TodoWrite to track implementation tasks
- Mark tasks complete as you progress
