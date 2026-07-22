# Implementation Findings: add-gemini-batch-processing

## Iteration 1

| ID | Type | Criticality | Finding | Disposition |
|----|------|-------------|---------|-------------|
| IMPL-001 | correctness | high | A canonical `<step>:<BIGINT>:<UUID>` request key can exceed the original 64-character database column. | Fixed by widening ORM, migration, and SQL contract columns to 128 and adding regression coverage. |
| IMPL-002 | resilience | high | Interrupted-submission recovery reclaimed every `submitting` job immediately, so a concurrent in-flight provider call could be released and submitted twice. | Fixed with a 15-minute stale threshold plus fresh/stale recovery tests. |
| IMPL-003 | correctness | high | Credential-key detection matched the substring `token`, rejecting legitimate Gemini config such as `max_output_tokens`. | Fixed with exact/suffix credential-key matching and positive/negative tests. |
| IMPL-004 | contract_mismatch | high | The checked-in SQL contract still described generic UUID targets and obsolete lifecycle states after the replan. | Fixed by aligning it with the integer content FK, claims, constraints, indexes, attempts, and timestamps. |
| IMPL-005 | workflow | medium | Work-package scopes and verification commands referenced pre-replan modules and test paths. | Fixed by reconciling package ownership, contract revision, and executable test paths. |

## Iteration 1 Result

All findings at or above the medium remediation threshold were fixed. No
known finding remains above the threshold; independent implementation review
and deployed validation remain pending.
