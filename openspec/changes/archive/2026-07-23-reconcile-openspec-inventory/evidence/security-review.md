# RI-03 security review

**Reviewer**: independent Codex security reviewer
**Date**: 2026-07-23
**Status**: Clean sign-off after rework

The security skill's referenced `references/security-checklist.md` was absent,
so the reviewer used its embedded OWASP preventive checklist.

## Findings and resolutions

1. **High — unsafe classifier artifacts**: The LLM-routing successor could
   have made the existing caller-path pickle loader production reachable. Its
   proposal, design, tasks, and delta now forbid executable production formats;
   require an allowlisted artifact root, containment, schema validation,
   authenticated integrity, and immutable revisions; and require tamper,
   traversal, symlink, malformed, and pickle-rejection tests.
2. **Medium — external alert data minimization**: The telemetry successor
   required source/resource identifiers and links but only secret redaction.
   It now requires opaque allowlisted identifiers; secret, PII, natural-key,
   and user-content redaction; same-origin diagnostic links with query and
   fragment removal; and deterministic sanitization tests.
3. **Medium — container provenance**: The ParadeDB successor checked
   pullability and digest equality without binding the digest to reviewed
   source. It now requires a reviewed commit plus trusted workflow or
   attestation, SBOM and vulnerability-scan evidence, and deployment by digest.

The reviewer found no secret leakage, shell injection, unsafe RI-03 mutation,
TLS bypass, or dynamic evaluation. The inventory validator is read-only and
uses `yaml.safe_load`.
