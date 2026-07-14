## ADDED Requirements

### Requirement: Public queued audio digest workflow

Every audio digest entry point SHALL submit the same PostgreSQL operation and SHALL call the public `AudioDigestWorkflow`. Transport code MUST NOT instantiate TTS providers, call generator private methods, or write local output outside the configured storage service.

#### Scenario: Equivalent audio digest interfaces
- **WHEN** equivalent audio digest requests are submitted through CLI, HTTP, MCP, or frontend
- **THEN** each enqueues the same operation type and normalized input
- **AND** completion links to a persisted `AudioDigest` using configured storage

#### Scenario: Workflow uses public generator API
- **WHEN** an audio digest job executes
- **THEN** it invokes the public audio digest generation method
- **AND** provider chunking and synthesis details remain behind the generator abstraction
