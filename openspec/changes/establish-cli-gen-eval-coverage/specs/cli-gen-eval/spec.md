## ADDED Requirements

### Requirement: The evaluation contract is repository-local and runner-independent

The repository SHALL own the evaluation contract — the interface descriptor,
scenario suites, and report schema — pinned to a declared framework contract
version, and SHALL validate those artifacts without installing the evaluation
runner.

#### Scenario: Contract validation with no runner installed

- **WHEN** contract validation runs and no evaluation runner is resolvable
- **THEN** the checked-in descriptor and every scenario SHALL be validated against
  the pinned schemas
- **AND** validation SHALL report a definite pass or fail
- **AND** SHALL NOT skip on account of the absent runner

#### Scenario: Dependency resolution without a runner

- **WHEN** dependency resolution runs in a clone with no evaluation runner and no
  adjacent framework checkout
- **THEN** resolution SHALL succeed
- **AND** no dependency, optional extra, or package source entry SHALL reference
  the evaluation framework

#### Scenario: The pinned contract version is declared

- **WHEN** the contract layer is loaded
- **THEN** the pinned framework contract version SHALL be read from a checked-in
  declaration
- **AND** the schemas used for validation SHALL be the ones vendored at that
  version

### Requirement: The runner is acquired as a pinned versioned artifact

The gate SHALL resolve the evaluation runner from a declared precedence of
versioned sources and SHALL NOT resolve it from a filesystem-adjacent checkout in
any enforcing context.

#### Scenario: Runner resolution precedence

- **WHEN** the gate resolves a runner
- **THEN** it SHALL prefer an explicit operator-supplied runner path
- **AND** SHALL otherwise resolve the pinned runner version recorded in the
  checked-in runner pin
- **AND** SHALL consider an adjacent framework checkout only when enforcement is
  not requested

#### Scenario: An adjacent checkout under enforcement

- **WHEN** enforcement is requested and the only candidate runner is a
  filesystem-adjacent framework checkout
- **THEN** the gate SHALL NOT use it
- **AND** SHALL fail reporting that no pinned runner was resolved

#### Scenario: The runner is isolated from project dependencies

- **WHEN** the pinned runner is installed
- **THEN** it SHALL be installed into an environment isolated from this project's
  environment
- **AND** the project's dependency manifest and lock file SHALL be unmodified
- **AND** the isolated runner's complete runtime and build dependency closure SHALL
  come from a checked-in lock that is required to be current

#### Scenario: Runner contract version mismatch

- **WHEN** a resolved runner reports a contract version other than the pinned one
- **THEN** the gate SHALL fail
- **AND** SHALL report both the pinned and the resolved version

#### Scenario: The runner is invoked through its published entry point

- **WHEN** the gate invokes the resolved runner, including any probe
- **THEN** it SHALL use the runner's published entry point as recorded in a single
  declared location
- **AND** SHALL forward only arguments the runner accepts

### Requirement: Runner availability is classified in three states

The gate SHALL distinguish an absent runner from an unrunnable one and SHALL NOT
report an invocation failure as an absence.

#### Scenario: No runner is resolvable locally

- **WHEN** no runner is resolvable at any precedence level and enforcement is not
  requested
- **THEN** the gate SHALL emit an advisory skip naming the sources it attempted
- **AND** SHALL exit successfully
- **AND** contract validation SHALL still have run and enforced

#### Scenario: No runner is resolvable under enforcement

- **WHEN** no runner is resolvable and enforcement is requested
- **THEN** the gate SHALL fail
- **AND** SHALL report each source it attempted

#### Scenario: A resolved runner cannot be invoked

- **WHEN** a runner is resolved but its probe invocation exits non-zero or rejects
  the gate's arguments
- **THEN** the gate SHALL fail regardless of whether enforcement was requested
- **AND** SHALL report the invocation and its captured diagnostic output
- **AND** SHALL NOT classify the condition as an absent runner

### Requirement: The checked-in evaluation suite covers the canonical CLI surface

The repository SHALL check in a schema-valid interface descriptor and a
categorized scenario suite covering the canonical `aca` command surface, with
read-only categories separated from mutating categories.

#### Scenario: Descriptor and scenarios are schema-valid

- **WHEN** the contract validator loads the checked-in descriptor
- **THEN** the descriptor SHALL validate against the pinned interface descriptor
  schema
- **AND** every scenario resolved from the descriptor's scenario directories SHALL
  validate against the pinned scenario schema

#### Scenario: Plumbing and discovery coverage

- **WHEN** the read-only categories execute
- **THEN** they SHALL cover the version and help surface of the top-level
  application and each registered command group
- **AND** SHALL cover capability discovery, configured-source listing, and durable
  operation listing
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
- **THEN** it SHALL submit every canonical workflow operation type through the CLI
- **AND** each submission SHALL return a durable operation handle

#### Scenario: Operation control coverage

- **WHEN** the operation-control category executes
- **THEN** it SHALL cover the operation retrieval, wait, retry, and cancel commands
  under their implemented command names
- **AND** SHALL observe at least one submitted operation through a terminal state

#### Scenario: The descriptor tracks the registered command surface

- **WHEN** a command group is registered on the CLI application
- **THEN** it SHALL appear in the descriptor, or in a reviewed exclusion set with a
  stated reason
- **AND** a drift check SHALL fail when neither holds

### Requirement: The evaluation target is resolved before backend-dependent categories run

The gate SHALL resolve the backend target that backend-dependent categories require, SHALL
classify it in the same three states it classifies the runner, and SHALL NOT report a run
as successful when a selected category's target is missing.

#### Scenario: A selected category requires an unreachable target

- **WHEN** a category containing scenarios against the canonical workflow surface is
  selected and the resolved target does not answer its health probe
- **THEN** the gate SHALL fail before executing the suite
- **AND** SHALL report the target it resolved and how it was resolved
- **AND** SHALL NOT execute the selection and attribute the resulting failures to the
  command under test

#### Scenario: No target can be named

- **WHEN** target resolution cannot determine a target at all
- **THEN** the gate SHALL fail
- **AND** SHALL distinguish this from a target that was named but did not answer

#### Scenario: The probe resolves the same target the scenarios will use

- **WHEN** the gate probes a target
- **THEN** the address SHALL be the one the command under test resolves from its own
  configuration
- **AND** the probe SHALL NOT invoke a command that the selected scenarios evaluate

#### Scenario: Running without a target is explicit and reported

- **WHEN** an operator requests a run restricted to scenarios that need no target
- **THEN** the gate SHALL execute only those scenarios
- **AND** SHALL report which categories' coverage was given up
- **AND** the request SHALL be refused when enforcement is requested

### Requirement: Category selection is enforced by the gate

The gate SHALL determine which scenarios a run evaluates and SHALL NOT rely on the runner
to filter them, so that an unselected category cannot execute.

#### Scenario: A run evaluates only the selected categories

- **WHEN** the gate runs with a category selection
- **THEN** the runner SHALL receive only the scenarios in that selection
- **AND** scenarios outside the selection SHALL NOT execute, whether or not the runner
  honours a category filter of its own

#### Scenario: A selection carries no residue from a previous run

- **WHEN** a narrower selection follows a wider one
- **THEN** only the narrower selection SHALL execute

#### Scenario: The coverage denominator survives selection

- **WHEN** the gate supplies the runner with a selection
- **THEN** the declared command surface used to compute coverage SHALL be unchanged from
  the checked-in descriptor

#### Scenario: A selection that cannot fit the runner is refused before it runs

- **WHEN** the selected scenarios exceed the pinned runner's per-tier capacity
- **THEN** the gate SHALL refuse before materializing the selection or invoking the
  runner
- **AND** SHALL name the tier that overflowed and by how much
- **AND** SHALL exit with the same code it uses for a report that cannot be believed

#### Scenario: An empty selection is refused

- **WHEN** a selection matches no scenarios
- **THEN** the gate SHALL fail
- **AND** SHALL NOT report a pass rate

### Requirement: Report validity and pass-rate threshold are both enforced

The gate SHALL enforce a documented pass-rate threshold and SHALL reject a report
that is malformed, empty, or incomplete before evaluating that threshold.

#### Scenario: `make gen-eval` emits a validated report

- **WHEN** `make gen-eval` runs with a resolved runner
- **THEN** it SHALL execute the checked-in descriptor and scenario suite
- **AND** SHALL emit a report that validates against the pinned report schema
- **AND** SHALL group results by command and category

#### Scenario: What the run was asked to do is recorded before it runs

- **WHEN** the gate resolves a selection
- **THEN** it SHALL record the scenarios that selection contains and the interfaces they
  address, before invoking the runner
- **AND** SHALL retain that record alongside the report

#### Scenario: A vacuous run is rejected

- **WHEN** a report contains no scenarios, or fewer scenarios than the recorded
  selection, or omits a scenario the selection contained
- **THEN** validation SHALL fail
- **AND** SHALL name the scenarios that were selected but not evaluated
- **AND** the gate SHALL NOT report success on the basis of the pass rate alone

#### Scenario: An interface the selection addresses is not evaluated

- **WHEN** a report omits an interface that the selected scenarios address, or reports
  such an interface as unevaluated
- **THEN** validation SHALL fail
- **AND** an interface outside the selection SHALL NOT cause a failure, because a
  category-scoped run is not required to cover the whole declared surface

#### Scenario: A report credits an interface the descriptor does not declare

- **WHEN** a report groups results under an interface that is neither declared by the
  descriptor nor listed in a reviewed exception set
- **THEN** validation SHALL fail

#### Scenario: An incomplete run is distinguished from a failing one

- **WHEN** validation rejects a report as incomplete, self-inconsistent, or out of range
- **THEN** the gate SHALL exit with a status distinct from the one it uses for a pass
  rate below the threshold
- **AND** SHALL do so regardless of the pass rate the report carries

#### Scenario: Continuous integration enforces without a skip path

- **WHEN** the evaluation gate runs in continuous integration
- **THEN** enforcement SHALL be requested with no advisory skip available
- **AND** the run SHALL fail when the pass rate is below the documented threshold
- **AND** failures SHALL be published as retained evidence grouped by command and
  category
- **AND** retained evidence SHALL omit raw step outputs, captured variables, diffs,
  and free-form failure text

#### Scenario: Continuous integration selects deterministic generation

- **WHEN** the gate runs in continuous integration
- **THEN** it SHALL use the runner's deterministic template-only generation mode
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

- **WHEN** a mutating category is selected with a target classified as production,
  or with a non-production target whose identity or origin resolves to a
  registered production identity or origin
- **THEN** the gate SHALL refuse to execute the category
- **AND** SHALL exit unsuccessfully without submitting any workflow

#### Scenario: The default pull-request run excludes mutating categories

- **WHEN** the evaluation gate runs on a pull request without explicit category
  selection
- **THEN** only the contract layer and read-only categories SHALL execute
- **AND** mutating categories SHALL require a separate, explicitly dispatched run

#### Scenario: The production guard is single-sourced

- **WHEN** the gate evaluates whether a target may be mutated
- **THEN** it SHALL consume the existing release-verification target policy model
  and its production deny registries
- **AND** SHALL NOT define an independent target classification

#### Scenario: The declared target is not the target the CLI will use

- **WHEN** a mutating category is selected with a valid non-production target policy
  whose API origin differs from the origin the CLI resolves from project settings
- **THEN** the gate SHALL refuse to execute the category
- **AND** SHALL report both origins, so the policy cannot be read as describing a
  target the scenarios are not pointed at

#### Scenario: The deployed target identity does not match protected policy

- **WHEN** a mutating category has an otherwise valid policy but its API health
  identity redirects, has untrusted provenance, or reports a revision other than
  the protected expected revision
- **THEN** the gate SHALL refuse to execute the category
- **AND** SHALL NOT execute any subprocess or forward a credential

#### Scenario: A refused mutation is distinguished from a malformed invocation

- **WHEN** the gate refuses a mutating category on target-policy grounds
- **THEN** it SHALL exit with a code reserved for that refusal and distinct from the
  usage, suite-failure, runner, target, and report-credibility codes
- **AND** SHALL report that no scenario was materialized and no workflow submitted

#### Scenario: The guard decides before any runner is resolved

- **WHEN** a mutating category is selected without a usable target policy and no
  evaluation runner is resolvable
- **THEN** the gate SHALL report the target-policy refusal rather than the runner
  state
- **AND** SHALL NOT execute any subprocess before reaching that verdict
