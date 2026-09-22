# Ship workstation and worker AppRole policies

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `ship-workstation-and-worker-approle-policies`
> Effort: S
> Priority: 4

## Summary

Add two AppRole policies to the bao-vault seed script, a workstation role limited to patch on secret/data/newsletter and a worker role with read plus patch on the same path.

## Dependencies

- None

## Acceptance Outcomes

- A write with the workstation AppRole succeeds for patch on secret/data/newsletter and is denied for read and delete.
- The worker AppRole succeeds for both read and patch on secret/data/newsletter and is denied for delete.
- The seed script is idempotent and re-running it leaves both policies unchanged.

## Rationale

Least-privilege roles let the workstation push cookies without reading LLM keys and let the worker persist rotated ct0 values, which the adapter write-back requires.
