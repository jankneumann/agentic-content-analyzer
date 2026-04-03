# Plan Findings: Obsidian Knowledge Integration

## Iteration 1

| # | Type | Criticality | Description | Status |
|---|------|-------------|-------------|--------|
| 1 | security | high | Path traversal risk in vault_path — no validation | Fixed: Added D8, spec scenario, tasks 1.5-1.6 |
| 2 | completeness | high | `_build_related_section()` had no spec requirement | Fixed: Added "Related section with wikilinks" requirement with 6 scenarios |
| 3 | consistency | high | `--since` unclear if applies to entities; collision format mismatch | Fixed: Clarified --since applies to time-stamped content only; collision uses numeric suffix -2, -3 |
| 4 | testability | high | JSON output schema undefined; Rich output unmeasurable | Fixed: Specified exact JSON schema and Rich table column structure |
| 5 | testability | high | Unresolved reference wikilink format vague | Fixed: Split into External reference and Unresolved reference scenarios with exact formats |
| 6 | performance | high | Unbounded entity/theme exports | Fixed: Added D13 (LIMIT on entity queries), D11 (streaming with yield_per), spec requirement for streaming |
| 7 | security | medium | YAML injection via unsanitized tags; manifest race condition | Fixed: Added D10 (tag sanitization), D9 (atomic manifest writes), spec scenarios for both |
| 8 | completeness | medium | No manifest corruption recovery scenario | Fixed: Added Corrupt manifest recovery and Atomic manifest writes scenarios |
| 9 | testability | medium | Content hash format unspecified; collision algorithm undefined | Fixed: Added Content hash format scenario (SHA-256, 64 chars, sha256: prefix); collision algorithm specified |
| 10 | feasibility | medium | Phase 3 could run parallel; _build_related_section moved too late | Fixed: Restructured — moved related section to Phase 2, Phases 3+4 can run parallel after Phase 2 |
| 11 | completeness | medium | No structured logging for export audit trail | Fixed: Added Structured logging requirement with 2 scenarios |
| 12 | testability | low | Neo4j warning format and export summary format unspecified | Fixed: Specified exact stderr warning text and summary table format |
