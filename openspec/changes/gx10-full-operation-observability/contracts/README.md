# Contracts: gx10-full-operation-observability

## OpenAPI

Primary additive API contract:

- contracts/openapi/v1.yaml

## Generated Types

- Python/Pydantic: contracts/generated/python/operation_observability.py
- TypeScript: contracts/generated/typescript/operation-observability.ts

These checked-in stubs freeze names and wire shapes for implementation. The implementation phase SHALL regenerate and compare them through the repository's chosen generator.

## SQL Schema

- contracts/sql/001_operation_observability.sql

The SQL is an implementation contract, not an executable migration. Alembic remains the migration mechanism.

## Event Schemas

- contracts/events/operation-context-v1.schema.json
- contracts/events/operation-attempt-v1.schema.json

## Compatibility

All new OperationHandle observability fields are nullable or optional for legacy jobs. Collection APIs remain summary-only. No contract exposes raw source payloads, prompts, exception stacks, or credentials.
