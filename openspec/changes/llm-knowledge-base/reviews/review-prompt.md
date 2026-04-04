# Plan Review: llm-knowledge-base

You are reviewing an OpenSpec proposal for a new feature. Read all plan artifacts below and produce ONLY valid JSON output conforming to the findings schema.

## Artifacts to Review

Read these files in the current working directory:

1. `openspec/changes/llm-knowledge-base/proposal.md` — What and why
2. `openspec/changes/llm-knowledge-base/design.md` — How (7 design decisions)
3. `openspec/changes/llm-knowledge-base/specs/knowledge-base/spec.md` — Requirements with scenarios
4. `openspec/changes/llm-knowledge-base/tasks.md` — Implementation tasks
5. `openspec/changes/llm-knowledge-base/contracts/openapi/v1.yaml` — API contract
6. `openspec/changes/llm-knowledge-base/contracts/db/schema.sql` — Database schema
7. `openspec/changes/llm-knowledge-base/work-packages.yaml` — Parallel execution plan

## Review Dimensions

Evaluate against: specification completeness, contract consistency, architecture alignment, security, performance, observability, compatibility, resilience, and work package validity.

## Output Format

Respond with ONLY this JSON structure (no markdown, no explanation):

```json
{
  "review_type": "plan",
  "target": "llm-knowledge-base",
  "reviewer_vendor": "<your-model-name>",
  "findings": [
    {
      "id": 1,
      "type": "<spec_gap|contract_mismatch|architecture|security|performance|style|correctness|observability|compatibility|resilience>",
      "criticality": "<critical|high|medium|low>",
      "description": "<what is wrong>",
      "resolution": "<how to fix it>",
      "disposition": "<fix|regenerate|accept|escalate>"
    }
  ]
}
```

Focus on HIGH and CRITICAL findings. Include at most 15 findings total.
