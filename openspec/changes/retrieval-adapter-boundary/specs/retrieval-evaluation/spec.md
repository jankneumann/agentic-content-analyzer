## Purpose

Provides labeled retrieval datasets and ranking-quality metrics so that retrieval
adapters can be compared on recall, ranking, and latency using the existing evaluation
persistence and command surface.

## ADDED Requirements

### Requirement: Retrieval Dataset Kind

The evaluation system SHALL support a `retrieval` dataset kind alongside the existing
LLM routing datasets. A retrieval sample SHALL consist of a query text, an ordered
list of relevant content identifiers, and an optional filter. Retrieval datasets SHALL
be created from explicit query and relevance pairs supplied by an operator, or seeded
from stored shadow-read comparisons where the primary adapter's top result is taken as
provisional relevance and marked as such.

#### Scenario: Operator creates a retrieval dataset

- **WHEN** an operator creates a dataset of kind `retrieval` with query and relevant-id pairs
- **THEN** the dataset and its samples are persisted
- **AND** the dataset lists as kind `retrieval` alongside routing datasets

#### Scenario: Provisional samples are labeled

- **WHEN** a retrieval dataset is seeded from shadow-read comparisons
- **THEN** every seeded sample is marked provisional
- **AND** reports distinguish provisional from operator-labeled samples

#### Scenario: Routing commands reject retrieval datasets

- **WHEN** a routing judge run or calibration targets a dataset of kind `retrieval`
- **THEN** the command fails with a message naming the dataset kind
- **AND** no judge calls are made

### Requirement: Retrieval Metrics

The evaluation system SHALL compute, per adapter and per search mode over a retrieval
dataset, recall at k for k in {5, 10, 20}, mean reciprocal rank, and p50 and p95 query
latency, and SHALL compute the top-k overlap between any two adapters. Metrics SHALL
be computed over the ranked content identifiers returned by the composition layer so
that adapters are compared after identical fusion and reranking.

#### Scenario: Metrics computed per adapter

- **WHEN** a retrieval comparison runs against two configured adapters
- **THEN** each adapter has recall@5, recall@10, recall@20, MRR, p50, and p95 recorded
- **AND** the pairwise top-10 overlap is recorded

#### Scenario: Missing relevant ids

- **WHEN** a sample's relevant identifiers no longer exist in the corpus
- **THEN** the sample is skipped and counted
- **AND** the report states how many samples were skipped

### Requirement: Retrieval Comparison Command

The evaluation command surface SHALL provide a retrieval comparison command that
accepts a retrieval dataset, one or more adapter names, and a search mode, runs each
query through the composition layer against each adapter, persists the resulting
metrics as evaluation results linked to the dataset, and prints a comparison table.
JSON output SHALL be a single document on standard output with diagnostics on
standard error.

#### Scenario: Comparison persisted

- **WHEN** the comparison command completes
- **THEN** one evaluation result row per adapter and mode is stored with the metric values
- **AND** re-running with the same inputs stores a new result rather than overwriting

#### Scenario: Unavailable adapter

- **WHEN** a requested adapter reports itself unavailable
- **THEN** the command exits non-zero naming the adapter
- **AND** no partial results are stored

#### Scenario: JSON output purity

- **WHEN** the command runs with JSON output
- **THEN** standard output contains exactly one JSON document
- **AND** all logging goes to standard error
