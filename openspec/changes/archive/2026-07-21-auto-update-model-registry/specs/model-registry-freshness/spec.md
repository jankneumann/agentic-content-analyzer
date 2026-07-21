# Model Registry Freshness

## ADDED Requirements

### Requirement: Live provider catalog discovery

The system SHALL enumerate provider model catalogs via their list-models APIs and
identify models absent from the registry.

#### Scenario: New model discovered from provider API
- **GIVEN** a provider with a configured API key and a model in its catalog not present in `settings/models.yaml`
- **WHEN** `aca models discover` runs
- **THEN** the model SHALL be reported as a candidate with its provider and model id

#### Scenario: Discovery degrades without a key
- **GIVEN** a provider with no configured API key
- **WHEN** discovery runs
- **THEN** that provider SHALL be skipped and recorded under failed providers
- **AND** discovery SHALL still report candidates from other providers

#### Scenario: Known models are not re-reported
- **GIVEN** a provider catalog whose models all exist in the registry
- **WHEN** discovery runs
- **THEN** no candidates SHALL be returned for that provider

### Requirement: Candidate enrichment

The system SHALL enrich each discovered candidate with cost and capability metadata.

#### Scenario: Candidate enriched with pricing and capabilities
- **GIVEN** a discovered candidate model
- **WHEN** enrichment runs via the pricing extractor
- **THEN** the candidate SHALL carry `cost_per_mtok_input`, `cost_per_mtok_output`, `context_window`, `max_output_tokens`, and capability flags (`supports_video`, `supports_audio`)
- **AND** fields that cannot be resolved SHALL be marked unknown rather than fabricated

### Requirement: Validate-before-promote gate

The system SHALL validate a candidate against the incumbent on a pipeline step
before recommending it as that step's default.

#### Scenario: Candidate passes the gate
- **GIVEN** a candidate proposed for step `youtube_processing` and an incumbent default
- **WHEN** `aca models propose-default --step youtube_processing --candidate <model>` runs
- **THEN** an evaluation dataset SHALL be created comparing incumbent vs candidate on that step
- **AND** N-judge consensus SHALL be computed
- **AND** a promotion recommendation SHALL be emitted only if quality parity meets the target AND cost is within budget

#### Scenario: Candidate fails the gate
- **GIVEN** a candidate whose consensus quality is below the parity target
- **WHEN** the gate runs
- **THEN** no promotion SHALL be recommended
- **AND** the failing metrics SHALL be reported

### Requirement: Risk-gated writeback

The system SHALL apply registry changes according to risk tier, with versioning
and audit, and SHALL NOT change step defaults without approval.

#### Scenario: Pricing diff auto-applies
- **GIVEN** a pricing/spec diff to an existing registry model and the low-risk tier policy
- **WHEN** `aca models refresh --apply` runs
- **THEN** `settings/models.yaml` / `provider_model_configs` SHALL be updated with a version bump and audit record
- **AND** the change SHALL be reflected after `ConfigRegistry` reload

#### Scenario: Default swap requires approval
- **GIVEN** a candidate that passed the gate and is proposed as a step default
- **WHEN** writeback is attempted without approval
- **THEN** the default SHALL NOT change
- **AND** the change SHALL be recorded as pending approval per `approval.yaml`

#### Scenario: Dry-run by default
- **GIVEN** `aca models refresh` invoked without `--apply`
- **WHEN** it runs
- **THEN** it SHALL report diffs and candidates without modifying any file

### Requirement: Scheduled refresh

The system SHALL support running the discover → enrich → gate → apply/propose flow
on a schedule.

#### Scenario: Scheduled job enqueues a refresh
- **GIVEN** a `refresh_models` entry in `settings/schedule.yaml` whose cron matches the current minute
- **WHEN** `AgentScheduler.tick()` runs
- **THEN** a model-refresh maintenance task SHALL be enqueued
- **AND** it SHALL not be enqueued more than once within the same minute
