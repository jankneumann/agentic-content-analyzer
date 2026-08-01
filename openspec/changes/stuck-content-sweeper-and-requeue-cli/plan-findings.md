# Plan findings

## Iteration 1: scaffold expansion

| # | Type | Criticality | Finding | Resolution |
|---|---|---|---|---|
| 1 | correctness | high | The scaffold had no operation/content mapping. | Initially restricted mapping to direct leaf payloads pending independent review. |
| 2 | concurrency | high | Stale retry could overlap its original handler. | Added advisory-lock serialization pending durable-fence review. |
| 3 | resilience | high | Retry had no atomic ceiling. | Designed an optional ceiling in canonical retry. |
| 4 | correctness | high | Completed operation state could fabricate domain completion. | Required durable output evidence. |
| 5 | auditability | high | Request audit could not prove per-item atomicity. | Added a same-transaction action audit contract. |
| 6 | performance | high | Candidate/history work was unbounded. | Added content-keyset page bounds and measured-plan requirements. |
| 7 | security | medium | Output fields were unspecified. | Added a closed non-sensitive planning schema. |
| 8 | consistency | medium | An older approved roadmap retained direct resets. | Flagged it for immediate supersession. |
| 9 | scope | medium | Periodic apply expanded risk before telemetry. | Kept explicit one-page dry-run/apply only. |

## Iteration 2: independent-review remediation

| # | Type | Criticality | Finding | Resolution |
|---|---|---|---|---|
| 1 | correctness | critical | Payload association did not prove current transition ownership, and canonical URL parsing had no leaf owner. | Added persisted Content operation/generation/phase ownership written by canonical URL and summary transitions; legacy unowned rows are report-only. |
| 2 | concurrency | critical | An old waiter could execute after the same row was reclaimed. | Added a dedicated claim generation incremented at every claim and required by pre-handler plus all lifecycle writes. |
| 3 | concurrency | critical | Advisory-lock connection loss allowed a continuing handler to commit. | Made job generation and Content ownership mandatory in every supported domain transaction; advisory lock is serialization only. |
| 4 | correctness | high | Old or forced Summaries could authorize a false completed projection. | Added Summary operation/generation provenance, exact-match projection, and force precedence. |
| 5 | cancellation | high | Stale retry could clear pending cancellation. | Added pre-handler cancellation checkpoint and cancellation-before-stale precedence. |
| 6 | transactionality | high | Opaque public retry could open a second connection inside apply. | Defined one physical apply connection, explicit lock order, and a connection-scoped locked retry primitive. |
| 7 | compatibility | high | Apply was unsafe during mixed-worker rollout. | Added default-off apply plus per-claim protocol-version rejection. |
| 8 | contract | high | Report fields could not prove retry before/after state. | Added explicit before/after content/operation/retry fields and proposed/observed projection mode. |
| 9 | consistency | high | Canonical operation/job/CLI changes lacked delta specs. | Added change-local deltas for all three affected capabilities. |
| 10 | persistence | medium | Audit/provenance schema constraints were prose-only. | Added an exact DB contract with checks, no destructive FKs, append-only trigger, indexes, and downgrade requirements. |
| 11 | performance | medium | JSON owner lookup could not safely classify malformed/v2 payloads. | Removed payload lookup entirely; candidate join uses persisted Content ownership. |
| 12 | API | medium | Status codes, pagination, and CLI exit behavior were ambiguous. | Defined synchronous 200 reports, 401/403/422/503 errors, one-page traversal, and exact exit policy. |
| 13 | configuration | medium | Stale/budget/apply settings lacked safe bounds. | Added concrete names, defaults, limits, and cross-field constraints. |
| 14 | planning | medium | The duplicate roadmap remained executable during implementation. | Marked it `replan_required` and replaced its source proposal section in this planning change. |

## Iteration 3: final-review remediation

| # | Type | Criticality | Finding | Resolution |
|---|---|---|---|---|
| 1 | recovery | critical | Canonical URL extraction failure completed as partial, while retry hit duplicate detection. | Persist exact-content webpage failure evidence, fail the operation retryably, and resume `URLExtractor` directly on the same row. |
| 2 | concurrency | critical | Content ownership at generation N could not roll to retry generation N+1. | Added a narrow current-claim acquisition CAS for the same operation/phase from unowned predecessor or older failed ownership. |
| 3 | compatibility | critical | A legacy claimant could inherit protocol 2 from an earlier current worker. | Added a database trigger resetting protocol to 1 on every transition to queued; only the current claim sets 2. |
| 4 | consistency | high | Unsupported status writers could retain a plausible old owner tuple. | Added positive owner versions plus a database trigger that clears unchanged ownership on status transitions, with ORM parity coverage. |
| 5 | determinism | high | URL retry could reclassify or redirect to a different route. | Recovery consumes the persisted webpage route and content ID without aggregate routing. |
| 6 | packaging | high | OperationService lifecycle fencing was outside the package allowed to implement it. | Sequenced lifecycle/retry before domain fencing and expanded its file/test scope. |
| 7 | cancellation | medium | Guard rejection could flow into generic job failure. | Added typed cancelled/superseded claim outcomes and terminal cancellation behavior. |
| 8 | persistence | medium | Owner constraints allowed generation zero and incompatible status/phase pairs. | Tightened Content, Summary, and action-audit constraints to positive compatible ownership. |
| 9 | contract | medium | Wire `limit=50` conflicted with a configurable server default below 50. | Removed the wire default; omitted limit uses configuration and explicit limit is capped by it. |
| 10 | testing | medium | Real summarizer suites and end-to-end URL recovery were outside package verification. | Added the actual summarizer paths, unsupported-writer regression, and failure-to-apply-to-success integration case. |
| 11 | recovery | critical | Stale apply requeued a transitional owner that N+1 was forbidden to acquire. | Apply now moves Content to owned `failed` with an advanced owner version before retry; parsing and processing renewal tests trace the full transition. |
| 12 | packaging | high | Lifecycle fencing preceded the shared claim context it needed. | The lifecycle/retry package now owns the base claim context before downstream domain fencing extends it. |
| 13 | checkpoint | medium | Canonical retry cleared the URL resume result that direct recovery consumes. | Retry tasks now conditionally preserve only the exact validated URL recovery checkpoint while retaining ordinary stale-result clearing. |
| 14 | crash safety | high | Process loss could occur after owned Content failure but before resume-result attachment. | Retry now falls back to exactly one Content row owned by its own parsing operation; zero or multiple rows fail closed. |
| 15 | contract | medium | The preserved URL resume result lacked a closed structural predicate. | Defined a strict v2 command/route/status/outcome/single-ID/diagnostic/owner profile with malformed-result tests. |
| 16 | traceability | medium | Package and contract metadata still identified revision 2. | Bumped both handoff/cache revisions to 3. |

Iteration 3 remediates every critical, high, and medium finding from the final
independent pass. Three independent re-review lanes report no remaining critical,
high, or medium findings, so the plan is converged for implementation.
