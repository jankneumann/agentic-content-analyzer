## MODIFIED Requirements

### Requirement: Memory Provider

The system SHALL persist and recall agent memory through a configurable provider built from
settings, supporting a hybrid recall strategy across prior tasks and insights, and SHALL report
partial persistence truthfully.

#### Scenario: Store and recall with hybrid strategy
- **WHEN** an agent stores a memory entry and a subsequent recall query is made
- **THEN** the memory provider SHALL query all configured strategies (graph, vector, keyword) in parallel
- **AND** merge results using weighted Reciprocal Rank Fusion
- **AND** apply recency and frequency weighting to the merged results
- **AND** return deduplicated, ranked memory entries
- **AND** update `access_count` and `last_accessed_at` for returned entries

#### Scenario: Memory strategy configuration
- **WHEN** a memory provider is initialized with a strategy configuration dict (e.g., `{"graph": 0.4, "vector": 0.4, "keyword": 0.2}`)
- **THEN** the provider SHALL support any combination of `graph`, `vector`, `keyword`
- **AND** accept per-strategy weight configuration (0.0 to 1.0)
- **AND** gracefully degrade if a backend is unavailable (e.g., Neo4j down → skip graph strategy)
- **AND** log warnings for unavailable strategies without failing

#### Scenario: Memory strategies are built from settings
- **WHEN** the durable worker constructs the conductor
- **THEN** it SHALL build the provider with `build_memory_strategies(settings)` using the weights in `agent_memory_strategies` (default keyword 0.6, vector 0.4)
- **AND** it SHALL NOT construct a provider with an empty strategy map
- **AND** a strategy whose backend is not configured SHALL be omitted with a logged warning rather than failing task execution

#### Scenario: Vector strategy validates the embedding dimension
- **WHEN** the factory builds the vector strategy
- **THEN** it SHALL compare the `agent_memories.embedding` column dimension with the configured embedding provider's dimension
- **AND** on mismatch it SHALL disable the vector strategy with a warning that names both dimensions
- **AND** keyword recall SHALL continue to work

#### Scenario: Partial store is reported
- **WHEN** `store` succeeds on at least one strategy and fails on another
- **THEN** it SHALL return a `MemoryStoreOutcome` with `status = "partial"` and a per-strategy outcome map
- **AND** the memory ID SHALL be the same across every strategy that stored it
- **AND** the conductor SHALL log the partial outcome at warning level and record it in memory telemetry

#### Scenario: Store fails on every strategy
- **WHEN** no strategy stores the entry
- **THEN** `store` SHALL return `status = "failed"` without raising
- **AND** task execution SHALL continue

### Requirement: Approval Gates

The system SHALL classify task risk and require human approval before executing actions above
the configured risk threshold, honoring per-persona overrides, and SHALL express a pending
approval as a durable `approval.wait` child operation of the agent task.

#### Scenario: Risk classification with persona overrides
- **WHEN** the conductor is about to delegate to a specialist under a specific persona
- **THEN** it SHALL resolve the risk of `delegate.<specialist>` as persona `approval_overrides` > base `settings/approval.yaml` > default MEDIUM
- **AND** `settings/approval.yaml` SHALL define `delegate.research`, `delegate.analysis`, `delegate.synthesis`, and `delegate.ingestion`
- **AND** LOW SHALL execute immediately, MEDIUM SHALL execute and log, HIGH and CRITICAL SHALL block
- **AND** persona overrides SHALL only lower risk levels, never escalate them

#### Scenario: Blocking creates a durable approval
- **WHEN** a delegation resolves to HIGH or CRITICAL
- **THEN** the system SHALL create an `approval_requests` row with status `pending`, the action, risk level, and context
- **AND** submit an `approval.wait` child operation linked to that row
- **AND** set the agent task status to `blocked`
- **AND** defer the parent operation with `wait_on = "children_terminal"` so it is not re-claimed until the child is terminal

#### Scenario: Gate is constructed from configuration
- **WHEN** the durable worker constructs the conductor
- **THEN** it SHALL build `ApprovalGate` from the loaded `settings/approval.yaml` risk map and the active persona's overrides
- **AND** a task SHALL NOT fail because the gate was constructed without configuration

### Requirement: Conductor Agent

The conductor SHALL accept tasks from users and from the scheduler, plan them against the
active persona and prior memory, delegate sub-tasks to specialists, and drive each task through
its status lifecycle to completion or failure as a durable `agent_task.execute` operation.

#### Scenario: User submits a research task
- **WHEN** a user submits a task via API or CLI
- **THEN** the system SHALL create an `agent_tasks` record with status `received`
- **AND** submit one `agent_task.execute` operation whose normalized input is `{task_id, prompt, task_type, persona, params}`
- **AND** the conductor SHALL load the active persona, query memory, plan with `LLMRouter.generate_with_planning()`, delegate, synthesize, store insights, and mark the task `completed`
- **AND** the operation handle SHALL carry the `agent_task` resource on completion

#### Scenario: Repeated submission is idempotent
- **WHEN** the same prompt, task type, persona, and params are submitted again while the first operation is active
- **THEN** the existing operation handle SHALL be returned and no second task SHALL run

#### Scenario: Scheduler triggers a proactive task
- **WHEN** the current time matches a cron expression in `settings/schedule.yaml`
- **THEN** the scheduler SHALL submit the same `agent_task.execute` operation with `source = schedule` and the configured priority
- **AND** it SHALL skip submission when a previous run of the same schedule is still active

#### Scenario: Task requires human approval
- **WHEN** a delegation blocks on approval
- **THEN** the conductor SHALL return a deferred result whose checkpoint records the plan, the next sub-task index, partial results, accumulated cost and tokens, and the approval operation ID
- **AND** on approval the conductor SHALL resume at the recorded index with partial results restored and SHALL NOT re-plan
- **AND** on denial the conductor SHALL re-plan once with the denial reason in context, and SHALL fail the task with that reason if the new plan blocks on the same action

#### Scenario: Task failure and recovery
- **WHEN** a specialist fails during execution and the conductor receives the failure
- **THEN** it SHALL log the error with full context
- **AND** decide whether to retry, delegate to a different specialist, or adjust the plan
- **AND** mark the task `failed` with error details when all retries are exhausted
- **AND** store any partial results as insights with reduced confidence

#### Scenario: Cost is accumulated from specialist spend
- **WHEN** a specialist completes a generation
- **THEN** its result metadata SHALL include `cost` computed by `BaseAgent.calculate_cost`
- **AND** the conductor SHALL accumulate `cost` (or `cost_usd` when present) into `cost_total`
- **AND** `agent_tasks.cost_total` SHALL be non-zero for any task that made a model call
