# Establish CLI gen-eval coverage

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `establish-cli-gen-eval-coverage`
> Effort: L
> Priority: 6

## Summary

Add the supported gen-eval runner, checked-in CLI descriptor and scenarios, Make target, report validation, and CI threshold. Categorize read-only discovery and validation separately from staging-only submission and terminal workflow behavior.

## Dependencies

- `ri-03`
- `ri-04`

## Acceptance Outcomes

- make gen-eval executes the checked-in descriptor and scenario suite and emits a schema-valid report.
- Scenarios cover version and help, discovery, validation, every canonical workflow operation type, and operation wait, status, retry, and cancel commands.
- CI enforces a documented pass-rate threshold and publishes failures grouped by command and category.
- Mutating scenarios require an explicit staging or ephemeral target and reject production by default.

## Rationale

The remembered evaluation suite is absent, leaving key command behavior unmeasured outside mocked tests.
