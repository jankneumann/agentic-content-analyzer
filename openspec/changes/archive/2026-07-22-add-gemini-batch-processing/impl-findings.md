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

## Independent Review

The configured external reviewers were attempted first. Claude returned an
adapter error and Gemini exceeded the 300-second dispatch timeout, so the
documented inline fallback reviewed the core adapter and orchestration/CLI
surfaces. The fallback review found the following issues.

| ID | Type | Criticality | Finding | Disposition |
|----|------|-------------|---------|-------------|
| IMPL-006 | resilience | critical | Per-call Gemini async clients were not closed, leaking transports and event-loop resources. | Fixed by closing `client.aio` in a `finally` block, suppressing close-only failures after a provider result, and covering success, provider failure, and close failure. |
| IMPL-007 | correctness | low | `batch_config()` shallow-copied the global config and allowed nested caller mutation to leak across requests. | Fixed by copying the nested execution mapping and adding a mutation-isolation test. |
| IMPL-008 | correctness | critical | Result-handler exceptions could leave partial ORM mutations in the poll transaction or poison the session after a flush error. | Fixed by applying each handler inside a nested transaction and testing both partial mutation and integrity failures. |
| IMPL-009 | resilience | critical | A process interruption during synchronous fallback could repeat an external call without consuming the configured attempt budget. | Fixed by committing the attempt before the call and isolating fallback/result handling in a savepoint; a second-session cancellation test proves durability. |
| IMPL-010 | security | critical | Credential screening checked only the config mapping and could persist secrets embedded in structured request contents. | Fixed by validating the complete request payload recursively before persistence. |
| IMPL-011 | spec_gap | high | `aca batch status` returned aggregates but omitted the required recent-job details. | Fixed with a bounded newest-ten query and JSON-safe job summaries in both output modes. |
| IMPL-012 | performance | low | The submit sweep loaded every pending request before selecting a bounded provider batch. | Fixed with grouped count/age aggregation followed by a bounded, lock-aware claim query per ripe group. |

## Independent Review Result

All seven findings were remediated. Focused regression tests cover every
critical and high-severity finding. No known blocking implementation-review
finding remains; final validation is pending.
