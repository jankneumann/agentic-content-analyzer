# Plan Review: tree-index-chunking

You are reviewing an OpenSpec proposal for a "Tree Index Chunking" feature. Your task is to produce structured findings as JSON.

## Artifacts to Review

Read ALL of the following files before producing findings:

1. `openspec/changes/tree-index-chunking/proposal.md` — What and why
2. `openspec/changes/tree-index-chunking/design.md` — How (architecture, algorithms, cost analysis)
3. `openspec/changes/tree-index-chunking/tasks.md` — Work decomposition with dependencies
4. `openspec/changes/tree-index-chunking/specs/document-search/spec.md` — Formal requirements and scenarios

## Also read for context (existing code):

5. `src/services/chunking.py` — ChunkingStrategy protocol (line ~129), STRATEGY_REGISTRY (~518), ChunkingService.chunk_content() (~565)
6. `src/models/chunk.py` — DocumentChunk ORM model, ChunkType enum
7. `src/services/indexing.py` — index_content() function, _run_async() pattern
8. `src/services/search.py` — HybridSearchService, RRF fusion
9. `src/models/search.py` — SearchResult model
10. `src/config/models.py` — ModelStep enum, model resolution

## Review Dimensions

Evaluate against:
- **Specification completeness**: All requirements use SHALL/MUST, are testable, have scenarios
- **Architecture alignment**: Design follows existing codebase patterns (Semaphore for concurrent LLM, ModelStep enum for model config, raw SQL for vector columns, etc.)
- **Security**: Input validation, LLM prompt injection risks, resource exhaustion bounds, data integrity
- **Work package validity**: Task dependencies are correct, no file-overlap conflicts, tasks are single-commit sized

## Output Format

Output ONLY valid JSON (no markdown fencing, no commentary). Conform to this structure:

```json
{
  "review_type": "plan",
  "target": "tree-index-chunking",
  "reviewer_vendor": "<your-model-name>",
  "findings": [
    {
      "id": 1,
      "type": "<spec_gap|contract_mismatch|architecture|security|performance|correctness>",
      "criticality": "<critical|high|medium|low>",
      "description": "Clear description of the issue found",
      "resolution": "Recommended fix",
      "disposition": "<fix|accept|escalate>"
    }
  ]
}
```

Finding types: spec_gap (missing requirement), architecture (design pattern issue), security (vulnerability), performance (latency/resource issue), correctness (logical error).

Dispositions: fix (must fix before implementation), accept (minor, OK as-is), escalate (needs human decision).

Be specific — reference file names, line numbers, task IDs, and setting names. Do not produce false positives for things the plan already handles correctly.
