# Design: Deployable evaluation-to-routing loop

## Required architecture decisions

- One effective routing-config resolver with environment > DB > YAML
  precedence.
- A router factory that injects embedding and loads an immutable, versioned
  classifier artifact. Production routing SHALL NOT deserialize pickle or
  another executable object format.
- A dataset contract sourced from persisted pipeline provenance or an explicit
  import, not an empty record.
- A bootstrap-free evaluation → training → calibration → enablement sequence.
- Durable execution for long-running evaluation/training if exposed remotely.
- Accurate per-call selected-model cost and terminal failure persistence.

## Safety

Dynamic routing remains opt-in. Enablement must be atomic, reversible, and tied
to a validated classifier/config revision. Failed embedding or classifier load
falls back to fixed routing with observable reasons.

Classifier artifacts use a non-executable, schema-validated representation.
Every path is resolved beneath an allowlisted artifact root; traversal,
symlink escape, arbitrary caller-supplied locations, and unsupported formats
are rejected. Immutable revision metadata includes an authenticated signature
or trusted checksum resolved from protected configuration. Loading verifies
integrity and schema before construction. Tests cover tampering, malformed
artifacts, path traversal, symlink escape, and safe fallback. Any legacy pickle
conversion is an offline, explicitly trusted migration step and is never
reachable from a production request or routing-config path.
