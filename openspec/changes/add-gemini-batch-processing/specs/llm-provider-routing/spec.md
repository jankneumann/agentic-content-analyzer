# Spec Delta: LLM Provider Routing

## ADDED Requirements

### Requirement: Gemini-only batch adapter

The router SHALL resolve logical Gemini model IDs to Google AI provider IDs for
batch submission and SHALL reject non-Google providers before an SDK call.

#### Scenario: Non-Google model is rejected

- **WHEN** batch submission receives a model without a Google AI provider route
- **THEN** it SHALL raise a validation error before creating a provider client
