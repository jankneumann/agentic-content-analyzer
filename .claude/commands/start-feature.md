---
allowed-tools: Bash(git checkout:*)
argument-hint: Describe new feature
description: Steps to do after finishing a feature
---

Create a new feature branch where the name is based on the feature description $ARGUMENTS.

Compact context to only what is needed to implement a new feature.

Start in planning mode and follow the guidelines and architecture descriptions in @CLAUDE,md and @docs/*.md when defining the implementation plan.

Always start the implementation with the tests that need to pass before implementing the rest of the code.
