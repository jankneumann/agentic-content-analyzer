# Design: Source override closeout

## Decisions to make

1. Choose whether the discriminator remains nested in `config` or is projected
   top-level, then align OpenAPI, server, clients, and tests.
2. Preserve PATCH as the canonical enable/disable mutation unless a concrete
   compatibility requirement proves otherwise.
3. Test actual settings components and browser behavior, not only API clients.
4. Exercise the Alembic upgrade contract against a disposable database.
5. Record PATCH semantics in current durable design documentation or an ADR;
   never edit the dated source archive.

## Non-goals

- Replacing the source capability registry.
- Changing database-over-YAML precedence.
- Reintroducing direct ingestion from settings mutations.
- Modifying `openspec/changes/archive/2026-07-23-db-source-overrides/**`.
