Review the committed implementation of OpenSpec change
`add-gemini-batch-processing` against its revised proposal, design, specs,
contracts, tasks, and work packages.

The implementation is intentionally core-only: no production ingestion or
YouTube call site may opt into batching. Inspect the feature-specific diff from
the merge base, while treating the current parent branch as baseline.

Focus on persistence/migration correctness, async `google-genai` Batch API
usage, metadata correlation, byte limits, concurrent claim and crash recovery,
idempotent reconciliation, bounded fallback, advisory-lock worker integration,
safe defaults, read-only CLI behavior, assumptions-based cost reporting, and
regression coverage. Check that no free-form queue operation was added.

Output ONLY valid JSON conforming to `review-findings.schema.json`, including
`axis`, `severity`, matching severity prefixes, `file_path`, and `line_range`
for code findings. Use target/package_id `whole-branch`.
