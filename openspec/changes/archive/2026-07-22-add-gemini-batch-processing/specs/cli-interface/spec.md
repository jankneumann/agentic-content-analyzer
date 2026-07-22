# Spec Delta: CLI Interface

## ADDED Requirements

### Requirement: Gemini batch operator commands

The CLI SHALL expose read-only `batch status` and SHALL support canonical root
`--json` output without stray human-readable text.

#### Scenario: JSON batch status is machine readable

- **WHEN** a user runs `aca --json batch status`
- **THEN** stdout SHALL contain exactly one valid JSON document
