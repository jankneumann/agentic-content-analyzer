## ADDED Requirements

### Requirement: The gen-eval framework is consumed externally, never as a dependency

The repository SHALL resolve the gen-eval framework from an externally owned
checkout at run time and SHALL NOT declare it as a package dependency, path
source, or vendored copy.

#### Scenario: Dependency resolution without a framework checkout

- **WHEN** `uv lock` or `uv sync` runs in a clone with no sibling
  `agentic-coding-tools` checkout present
- **THEN** resolution SHALL succeed
- **AND** no dependency, optional extra, or `[tool.uv.sources]` entry SHALL
  reference the gen-eval package

#### Scenario: Framework invocation form

- **WHEN** the gate invokes the framework, including its runnability probe
- **THEN** it SHALL invoke the framework as a Python module
- **AND** SHALL NOT depend on the framework's console-script entry point

#### Scenario: Framework location is configurable

- **WHEN** `ACA_GEN_EVAL_PROJECT` names a framework checkout
- **THEN** the gate SHALL resolve the framework from that path
- **AND** SHALL otherwise fall back to the documented default sibling path

### Requirement: Framework availability is classified in three states

The gate SHALL distinguish an absent framework from an unrunnable one and SHALL
NOT report an invocation failure as an absence.

#### Scenario: The framework checkout is absent locally

- **WHEN** the resolved framework path does not exist and `ACA_GEN_EVAL_REQUIRE`
  is unset
- **THEN** the gate SHALL emit an advisory skip identifying the resolved path
- **AND** SHALL exit successfully

#### Scenario: The framework checkout is absent under enforcement

- **WHEN** the resolved framework path does not exist and `ACA_GEN_EVAL_REQUIRE`
  is set
- **THEN** the gate SHALL fail
- **AND** SHALL report the resolved path that was searched

#### Scenario: The framework is present but cannot be invoked

- **WHEN** the framework path exists but the probe invocation exits non-zero or
  rejects the gate's arguments
- **THEN** the gate SHALL fail regardless of `ACA_GEN_EVAL_REQUIRE`
- **AND** SHALL report the invocation and its captured diagnostic output
- **AND** SHALL NOT classify the condition as an absent checkout

### Requirement: The checked-in evaluation suite covers the canonical CLI surface

The repository SHALL check in a schema-valid interface descriptor and a
categorized scenario suite covering the canonical `aca` command surface, with
read-only categories separated from mutating categories.

#### Scenario: Descriptor and scenarios are schema-valid

- **WHEN** the gate loads the checked-in descriptor
- **THEN** the descriptor SHALL validate against the framework's interface
  descriptor schema
- **AND** every scenario resolved from the descriptor's scenario directories
  SHALL validate against the framework's scenario schema

#### Scenario: Plumbing and discovery coverage

- **WHEN** the read-only categories execute
- **THEN** they SHALL cover the version and help surface of the top-level
  application and each registered command group
- **AND** SHALL cover capability discovery, configured-source listing, and
  durable operation listing
- **AND** SHALL assert that machine-readable invocations emit exactly one JSON
  document on standard output with diagnostics confined to standard error

#### Scenario: Validation coverage

- **WHEN** the validation category executes
- **THEN** it SHALL cover rejection of malformed command arguments and invalid
  pagination cursors
- **AND** SHALL assert that absent optional values are omitted rather than
  serialized as empty query values

#### Scenario: Canonical workflow submission coverage

- **WHEN** the workflow-submission category executes
- **THEN** it SHALL submit every canonical workflow operation type through the
  CLI
- **AND** each submission SHALL return a durable operation handle

#### Scenario: Operation control coverage

- **WHEN** the operation-control category executes
- **THEN** it SHALL cover the operation retrieval, wait, retry, and cancel
  commands under their implemented command names
- **AND** SHALL observe at least one submitted operation through a terminal
  state

### Requirement: Report validity and pass-rate threshold are both enforced

The gate SHALL enforce a documented pass-rate threshold and SHALL reject a
report that is malformed, empty, or incomplete before evaluating that threshold.

#### Scenario: `make gen-eval` emits a validated report

- **WHEN** `make gen-eval` runs
- **THEN** it SHALL execute the checked-in descriptor and scenario suite
- **AND** SHALL emit a report that validates against the durable report schema
- **AND** SHALL group results by command and category

#### Scenario: A vacuous run is rejected

- **WHEN** a report contains fewer scenarios than the declared minimum for the
  selected categories, or omits a descriptor-declared interface from the tested
  interfaces
- **THEN** validation SHALL fail
- **AND** the gate SHALL NOT report success on the basis of the pass rate alone

#### Scenario: CI enforces the documented threshold

- **WHEN** the evaluation gate runs in continuous integration
- **THEN** enforcement SHALL be active with no advisory skip available
- **AND** the run SHALL fail when the pass rate is below the documented threshold
- **AND** failures SHALL be published as retained evidence grouped by command
  and category

#### Scenario: Continuous integration selects deterministic generation

- **WHEN** the gate runs in continuous integration
- **THEN** it SHALL use the framework's deterministic template-only generation
  mode
- **AND** SHALL NOT require model-provider credentials

### Requirement: Mutating scenarios require a non-production target

Mutating evaluation categories SHALL require an explicitly declared staging or
ephemeral target and SHALL reject production by default, reusing the existing
release-verification target policy rather than a second target model.

#### Scenario: A mutating category runs without an explicit target

- **WHEN** a mutating category is selected and no explicit non-production target
  policy is supplied
- **THEN** the gate SHALL refuse to execute the category
- **AND** SHALL exit unsuccessfully with a message naming the missing target

#### Scenario: A mutating category names a production target

- **WHEN** a mutating category is selected with a target classified as
  production, or with a non-production target whose identity or origin resolves
  to a registered production identity or origin
- **THEN** the gate SHALL refuse to execute the category
- **AND** SHALL exit unsuccessfully without submitting any workflow

#### Scenario: The default pull-request run excludes mutating categories

- **WHEN** the evaluation gate runs on a pull request without explicit category
  selection
- **THEN** only read-only categories SHALL execute
- **AND** mutating categories SHALL require a separate, explicitly dispatched run

#### Scenario: The production guard is single-sourced

- **WHEN** the gate evaluates whether a target may be mutated
- **THEN** it SHALL consume the existing release-verification target policy
  model and its production deny registries
- **AND** SHALL NOT define an independent target classification
