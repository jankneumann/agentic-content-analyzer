# Spec Delta: Settings Management

## ADDED Requirements

### Requirement: Batch settings use safe precedence

Batch settings SHALL load safe YAML defaults and SHALL allow
`GEMINI_BATCH_ENABLED` to override only the global switch.

#### Scenario: Environment override is isolated

- **GIVEN** `Settings(_env_file=None)` and no explicit batch environment value
- **WHEN** settings are loaded
- **THEN** Gemini batching SHALL be disabled
