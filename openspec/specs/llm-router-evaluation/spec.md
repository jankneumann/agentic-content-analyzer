# llm-router-evaluation Specification

## Purpose

Define the implemented LLM evaluation and routing foundation. Production
operationalization is tracked by `operationalize-llm-evaluation-routing`.

## Requirements

### Requirement: Evaluation persistence foundation

The system SHALL provide relational models and migrations for routing
configuration, datasets, samples, results, consensus, and routing decisions
with their implemented constraints and relationships.

#### Scenario: Evaluation records are persisted

- **WHEN** services create supported evaluation records
- **THEN** ORM relationships and database constraints SHALL retain dataset,
  sample, judge, consensus, and routing-decision identity

### Requirement: Static routing configuration primitives

Model configuration SHALL load per-step routing mode, strong/weak models,
threshold, and enabled state from YAML and environment overrides, with dynamic
routing opt-in and fixed routing as the safe default.

#### Scenario: Dynamic routing is disabled

- **WHEN** a step is fixed or dynamic routing is not enabled
- **THEN** model selection SHALL preserve fixed behavior
- **AND** SHALL not require a trained classifier

### Requirement: Complexity classifier primitives

`ComplexityRouter` SHALL support classification plus versionable
train/save/load primitives and SHALL fall back safely when no trained model or
embedding result is available.

#### Scenario: Classifier is unavailable

- **WHEN** classification is requested without a usable trained artifact
- **THEN** the primitive SHALL report the fallback condition
- **AND** callers SHALL be able to preserve fixed routing

### Requirement: Blinded evaluation and calibration primitives

The evaluation foundation SHALL load per-step criteria, randomize blinded
output order, parse structured judge verdicts with bounded retry, aggregate
available judges, and calibrate thresholds from sufficient evaluated samples.

#### Scenario: Judge outputs disagree

- **WHEN** successful judges return different preferences
- **THEN** consensus SHALL apply the implemented majority/tie rules
- **AND** SHALL retain individual verdicts and agreement information

#### Scenario: Calibration has insufficient samples

- **WHEN** evaluated input is below the configured minimum
- **THEN** calibration SHALL refuse to produce an enablement threshold

### Requirement: Implemented evaluation surfaces

The system SHALL expose only the currently implemented record-level evaluation
service, CLI commands, and authenticated API structures; they SHALL not imply
that production classifier injection or paired-dataset generation already
exists.

#### Scenario: Operator creates an evaluation dataset record

- **WHEN** an implemented CLI or API command creates a dataset record
- **THEN** the record SHALL be queryable through supported surfaces
- **AND** production data population and routing enablement SHALL remain
  separate until operationalized
