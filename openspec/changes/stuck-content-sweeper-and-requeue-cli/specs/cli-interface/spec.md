## ADDED Requirements

### Requirement: CLI reconciles one bounded content page remotely

The CLI SHALL expose `aca operations reconcile-content` as a remote-only,
dry-run-by-default command with explicit `--apply`, `--limit`, and
`--after-content-id` controls.

#### Scenario: Operator previews one page

- **WHEN** the command is invoked without `--apply`
- **THEN** it SHALL request one dry-run page and exit zero after rendering it

#### Scenario: Operator applies one page

- **WHEN** `--apply` is supplied
- **THEN** the CLI SHALL request one enabled apply page through WorkflowApiClient
- **AND** SHALL not connect directly to the application database

#### Scenario: Apply is disabled

- **WHEN** the server returns the apply-disabled RFC 7807 problem
- **THEN** CLI SHALL render the safe problem and exit nonzero
