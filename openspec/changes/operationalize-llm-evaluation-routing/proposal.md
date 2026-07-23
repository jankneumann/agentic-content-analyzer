# Change: Operationalize LLM evaluation and routing

## Why

The evaluation foundation contains models, classifier primitives, judges,
consensus, calibration, services, CLI, and API structures. It is not a
deployable routing loop: production routers do not inject a classifier,
database overrides are not effective runtime configuration, datasets are not
populated from real provenance, calibration has a bootstrap cycle, several
surface promises are absent, failures/costs are incomplete, and sklearn is not
a declared runtime dependency.

## Source and completed scope

- Extracted from archived `llm-router-evaluation`.
- Completed and excluded: evaluation schema/migration, YAML/env configuration
  primitives, optional `ModelStep` hook, classifier primitives, criteria,
  blinded judge, consensus, calibrator, record-level services, and existing
  CLI/API structures.
- This change SHALL operationalize those foundations rather than rebuild them.

## What Changes

- Resolve effective routing config with environment > database > YAML
  precedence in fresh runtime routers.
- Provide a production router factory with embedding and versioned classifier
  lifecycle, including an explicit sklearn dependency or a deliberate
  replacement.
- Replace production pickle loading with a non-executable, schema-validated
  artifact format stored beneath an allowlisted root and bound to immutable
  revision plus integrity metadata.
- Generate/import paired datasets from persisted provenance; train, calibrate,
  and atomically enable routing without a routing-decision bootstrap cycle.
- Align distinct judge/human/failure/cost semantics and remove or implement
  overclaimed CLI/API/docs.
- Prove one DB/API config update changes a fresh runtime, selects a weak model
  for an eligible prompt, and persists an accurate routing decision.

## Capability

- `llm-evaluation-routing-operations`

## Impact

Model configuration, router construction, evaluation services, dependencies,
CLI/API contracts, operation semantics, persistence, documentation, and
integration tests may change. State-changing long-running work must use the
canonical durable operation boundary.
