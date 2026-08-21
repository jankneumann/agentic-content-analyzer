# Plan Review — add-gx10-backup-scheme

You are an independent plan reviewer. Read the OpenSpec plan artifacts and produce
structured findings. Do NOT modify any file.

## Read these (read-only)

All paths are relative to the repository root:

- `openspec/changes/add-gx10-backup-scheme/proposal.md`
- `openspec/changes/add-gx10-backup-scheme/design.md`
- `openspec/changes/add-gx10-backup-scheme/tasks.md`
- `openspec/changes/add-gx10-backup-scheme/specs/backup-and-restore/spec.md`
- `openspec/changes/add-gx10-backup-scheme/specs/cli-interface/spec.md`
- `openspec/changes/add-gx10-backup-scheme/specs/database-provider/spec.md`
- `openspec/changes/add-gx10-backup-scheme/contracts/README.md`
- `openspec/changes/add-gx10-backup-scheme/contracts/schemas/backup-manifest.schema.json`
- `openspec/changes/add-gx10-backup-scheme/contracts/events/backup-freshness-alert.schema.json`
- `openspec/changes/add-gx10-backup-scheme/work-packages.yaml`

Cross-check the plan's claims against the live tree. The most relevant existing
code is:

- `src/api/health_routes.py` (readiness probe, `_check_backup_recency`)
- `src/contracts/workflow_alert_models.py` (`WorkflowAlertEnvelopeV1`, `WorkflowEventKey`, diagnostic-URL allowlist)
- `src/models/workflow_alert.py` and `alembic/versions/91c7d2e4f8a6_add_workflow_alert_persistence.py` (durable alert persistence and its CHECK constraints)
- `src/cli/restore_commands.py` (existing restore-from-cloud command)
- `src/config/settings.py` (`railway_backup_*`, `graphdb_provider`/`graphdb_mode`, storage providers)
- `pyproject.toml`, `railway/postgres/**`

## What this change is

The project is migrating from Railway to a self-hosted gx-10 host. The existing
pg_cron backup has never produced a backup. This change delivers the project's
first working disaster-recovery capability: a Python-orchestrated `aca backup`
CLI shelling out to native tools (`pg_dump`, `neo4j-admin`, `bao`, `age`,
`rclone`), a systemd timer, client-side `age` encryption, a bucket-side run
manifest, a de-gated freshness check, durable freshness alerting, provider-side
retention, and a generalized restore path.

## Review checklist

Evaluate: specification completeness (testable SHALL clauses, no ambiguity),
contract consistency (schemas vs specs vs the live Pydantic models and DB
constraints), architecture alignment, security (credential handling, secrets in
argv, blast radius of the encryption identity, least privilege), performance
(unbounded listings, hot-path network reads), observability, compatibility
(breaking changes to the alert envelope and its consumers), resilience
(partial failure, retries, silent-success modes), and work-package validity
(no DAG cycles, non-overlapping write scopes, every task owned by a package with
write access to the files it must change, verification steps appropriate).

Pay particular attention to whether any task requires writing a file that its
owning package's `scope.write_allow` does not cover or that `scope.deny`
excludes — a package that cannot write the files it needs is structurally
blocked.

## Output

Output ONLY a single valid JSON document conforming to
`openspec/schemas/review-findings.schema.json`. No prose before or after, no
markdown fences.

Shape:

```
{
  "review_type": "plan",
  "target": "add-gx10-backup-scheme",
  "reviewer_vendor": "<your model name>",
  "findings": [
    {
      "id": 1,
      "axis": "correctness|readability|architecture|security|performance",
      "severity": "critical|nit|optional|fyi|none",
      "type": "spec_gap|contract_mismatch|architecture|security|performance|style|correctness|observability|compatibility|resilience",
      "criticality": "low|medium|high|critical",
      "description": "<severity prefix>: <what is wrong and where>",
      "resolution": "<what should change>",
      "disposition": "fix|regenerate|accept|escalate",
      "file_path": "<optional path the finding relates to>"
    }
  ]
}
```

Rules:

- `axis` and `severity` are REQUIRED on every finding.
- The `description` MUST begin with the prefix matching `severity`:
  `Critical:` / `Nit:` / `Optional:` / `FYI:` / (no prefix for `none`).
- Keep `disposition` coherent with `severity`: `critical`/`nit` → `fix`;
  `optional`/`fyi`/`none` → `accept`; anything else → `escalate`.
- Do not emit zero findings. At minimum record `severity: none` positive
  observations naming what the plan got right.
- Do not invent file paths or line numbers. Only cite what you actually read.
