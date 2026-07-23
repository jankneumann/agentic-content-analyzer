# Reconciliation: LLM router evaluation

**Disposition**: Archive the implemented evaluation foundation; continue the
deployable loop in `operationalize-llm-evaluation-routing`.

## Verified foundation

Evaluation models/migration, YAML/env configuration primitives, optional
`ModelStep` hook, classifier primitives, criteria, blinded judge, consensus,
calibrator, and current record-level services/CLI/API structures exist.
RI-03 passed 127 focused tests with two expected skips.

## Outstanding operationalization

Production router construction does not inject the classifier; DB routing
overrides are not consumed; dataset creation does not populate paired samples;
training/calibration has a bootstrap gap; sklearn is not a direct runtime
dependency; human/distinct-judge, failure, endpoint, and cost promises are
incomplete.

The original compound task boxes remain unchecked because most describe
completion units that mix implemented primitives with these outstanding
promises. A reduced truthful foundation was published to
`openspec/specs/llm-router-evaluation/spec.md`; the legacy spec SHALL NOT sync
automatically.
