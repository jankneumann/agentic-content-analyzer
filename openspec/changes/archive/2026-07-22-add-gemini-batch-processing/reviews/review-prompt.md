Review the OpenSpec plan `add-gemini-batch-processing` against the current code.

Read proposal.md, design.md, tasks.md, all specs, contracts/README.md,
work-packages.yaml, plan-findings.md, and relevant repository code. Focus on
correctness, architecture, resilience, security, performance, scope, and testability.
The plan was intentionally narrowed to inert core infrastructure; do not demand
the deferred ingestion call-site rollouts unless the core cannot be useful or safe
without them.

Return only one JSON object conforming to
`openspec/schemas/review-findings.schema.json`, with review_type `plan`, target
`add-gemini-batch-processing`, your vendor in reviewer_vendor, and findings.
Every finding must include axis and severity, and its description must begin with
the matching `Critical:`, `Nit:`, `Optional:`, or `FYI:` prefix (severity `none`
needs no prefix). Critical/nit findings use disposition `fix`; optional/fyi/none
use `accept`, unless a true human decision requires `escalate`.
