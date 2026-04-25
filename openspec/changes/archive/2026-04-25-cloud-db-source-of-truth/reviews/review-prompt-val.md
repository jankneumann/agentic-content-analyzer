# Validation Review — cloud-db-source-of-truth

You are reviewing the **validation evidence** for the `cloud-db-source-of-truth` OpenSpec change. The IMPLEMENT phase produced 5 work packages, IMPL_REVIEW surfaced 1 CRITICAL + 5 HIGH + 3 MEDIUM + 7 LOW findings, IMPL_FIX resolved all CRITICAL/HIGH/MEDIUM + 2 LOW. A VALIDATE run then confirmed security + behavioral + CI-parity locally.

Your role: independent reviewer of the validation evidence against the spec. Produce ONLY a JSON findings document — do not modify files.

## Scope of review

**Branch**: `openspec/cloud-db-source-of-truth`, 13 commits on top of main (9929+ lines from IMPLEMENT + IMPL_FIX combined).

**Read in this order**:

1. **Validation report** — `openspec/changes/cloud-db-source-of-truth/reviews/validation-report.json`. Treat it as the claim; your job is to verify it.
2. **Spec + design** — `openspec/changes/cloud-db-source-of-truth/{proposal,design,tasks}.md` and `specs/**/spec.md` for the normative requirements.
3. **Contracts** — `openspec/changes/cloud-db-source-of-truth/contracts/openapi/v1.yaml` and `contracts/db/schema.sql`.
4. **Implementation** — the 13 commits' diff:
   - `src/api/middleware/{audit,auth,error_handler}.py`
   - `src/api/routes/{audit_routes,kb_search_routes,kb_routes,graph_routes,reference_routes}.py`
   - `src/api/kb_routes.py` (retrofit)
   - `src/api/schemas/{kb,graph,references}.py`
   - `alembic/versions/b7a1c9d5e2f0_add_audit_log_table.py`
   - `src/cli/{api_client,restore_commands,manage_commands}.py`
   - `src/mcp_server.py`
5. **Prior-round findings** — `reviews/findings-{claude,codex,gemini}-impl.json` list the 17 findings from IMPL_REVIEW. Verify the IMPL_FIX commit (`dce2486`) actually resolved each one.

## Review dimensions

For each dimension, emit a JSON finding if the claim in `validation-report.json` doesn't match reality, if an IMPL_REVIEW finding is inadequately resolved, or if a new defect was introduced by IMPL_FIX.

1. **Claim verification** — every "pass" in `validation-report.json` must correspond to actual code state (e.g., `ruff_touched_files: pass` means ruff actually passes on those files; `test_suite: 195 passed` means the count is accurate).
2. **IMPL_REVIEW resolution** — each of the 17 findings in `reviews/findings-*-impl.json` must be resolved by commits up to `dce2486`. Partial/cosmetic fixes flagged as a finding.
3. **Regression risk** — IMPL_FIX touched many files. Check for obvious regressions: did the Problem-body handler break existing routes? Does the audit middleware's new `audit_notes` merge respect earlier auth_failure logic? Did the Railway-safety guard break the happy path?
4. **Spec compliance on resolved items** — e.g., audit spec now mandates observability attributes — verify `audit.operation`, `audit.status_code`, `audit.write_failure` are set exactly where required.
5. **Blast-radius awareness for CRITICAL** — restore-from-cloud safety must be demonstrably hardened. Is there any path left where a misconfigured profile could still hit the Railway prod DB?

## Specifically verify these IMPL_FIX claims

- **C1 Railway safety**: `_resolve_target_db` rejects `railway_database_url` fallback AND rejects explicit `--target-db` matching `RAILWAY_DATABASE_URL` unless `--allow-remote-target`. Verify by reading `src/cli/restore_commands.py` + corresponding tests.
- **H1 Problem bodies**: every `/api/v1/{kb,graph,references,audit}` path returns `application/problem+json` on 401/403/404/409/422/504. Legacy paths unchanged.
- **H2 KB search parity**: HTTP and in-process modes return identical shapes for identical data — specifically `total_count` (full match count) and `last_compiled_at` (drop nulls, not fabricate).
- **H3 next_cursor**: HTTP and MCP in-process both use overflow.ingested_at.
- **H4 --strict-http**: real CLI flag in `mcp_server.main()`, stderr error + exit 2 on missing config.
- **M1 middleware order**: design.md D3a now matches code — code shows Trace → CORS → SecurityHeaders → Audit → Auth (outer → inner); CORS outside Auth for error-response headers.
- **M2 handler notes**: graph/extract-entities sets `notes.content_id`; kb/lint/fix sets `notes.corrections_applied + zero_diff`.
- **M3 MIGRATION.md**: has a "Merge gate" section the reviewer must enforce; agentic-assistant PR link is still a placeholder (acceptable pre-merge state).

## Output Format

Output **only** a JSON object:

```json
{
  "review_type": "val",
  "target": "cloud-db-source-of-truth",
  "reviewer_vendor": "<your-model-name-and-version>",
  "validation_report_verdict": "confirmed | partial | unverified | contradicted",
  "impl_review_resolution_status": {
    "C1_restore_safety": "resolved | partial | unresolved",
    "H1_problem_bodies": "resolved | partial | unresolved",
    "H2_kb_parity": "resolved | partial | unresolved",
    "H3_next_cursor": "resolved | partial | unresolved",
    "H4_strict_http": "resolved | partial | unresolved",
    "M1_middleware_order": "resolved | partial | unresolved",
    "M2_handler_notes": "resolved | partial | unresolved",
    "M3_migration_md": "resolved | partial | unresolved"
  },
  "findings": [
    {
      "id": "VR-001",
      "type": "claim_unverified | regression | spec_gap | security | contract_mismatch | test_coverage | correctness | documentation | style",
      "criticality": "low | medium | high | critical",
      "description": "<specific issue with file:line references>",
      "resolution": "<actionable fix>",
      "disposition": "fix | accept | escalate"
    }
  ]
}
```

## Important

- You are an **independent** reviewer. Do not coordinate with other reviewers.
- Focus on **substantive** issues. Cite file:line where possible.
- Empty `findings` is acceptable if everything checks out.
- Your output is consumed by an automated synthesizer — deterministic JSON only.
