# Design: Add x_bookmarks to the workflow contract and ContentSource enum

## Decisions

- **Naming.** The command kind and source are `x_bookmarks` (snake_case, like
  `huggingface_papers`), and the response command is `ingest.x-bookmarks`
  (hyphenated, like `ingest.huggingface-papers`). The CLI derives
  `aca ingest x-bookmarks` from the kind.
- **No date bound.** Unlike most scheduled commands there is no `after_date` or
  `days_back`: X does not expose the time a post was bookmarked, so the adapter
  stops incrementally when a whole page is already known. `full` overrides that
  stop. The ri-10 bulk planner therefore ignores the planner's `after_date`.
- **`max_items` is capped at 10000.** The source is an unofficial, rate-limited
  GraphQL surface; an upper bound keeps one request from walking an unbounded
  history. The source config's `max_entries` supplies the default in ri-10.
- **`expand_links` has no default.** An absent value means "use the configured
  source", so a manual run cannot silently flip the configured behaviour.
- **No credentials in the command.** `auth_token` and `ct0` are resolved
  server-side through the credential provider; a contract test asserts that the
  schema has no credential-shaped fields.
- **Downgrade is a no-op.** PostgreSQL cannot drop an enum value in place,
  matching the Obsidian and Readwise migrations.

## Non-goals

Registering the descriptor, config model, YAML, fixture, adapter, or worker
dispatch (ri-10 and ri-11).
