## ADDED Requirements

### Requirement: X bookmarks source descriptor

`SOURCE_REGISTRY` SHALL register a scheduled `x_bookmarks` descriptor named
"X Bookmarks" for `XBookmarksIngestCommand`, emitting
`ContentSource.X_BOOKMARKS`, supporting `force_reprocess`, and matching
`XBookmarksSource` configuration through `get_x_bookmarks_sources()`. Its
scheduled planner SHALL produce one command whose `max_items` is the configured
`max_entries` and whose `expand_links` is the configured value, and SHALL
ignore the pipeline period because X does not expose when a post was
bookmarked. The capability document SHALL list `x_bookmarks` in the same
position as the contract discriminator mapping.

#### Scenario: Capability parity

- **WHEN** the capability document is compared with the `IngestCommand` discriminator mapping
- **THEN** the source keys, order, and fields match, including `x_bookmarks`

#### Scenario: Planner maps configuration and ignores the period

- **WHEN** an enabled source with `max_entries: 40` and `expand_links: true` is planned for two different periods
- **THEN** both plans are one command with `max_items: 40` and `expand_links: true` and no date field

### Requirement: X bookmarks readiness requires the full session

The `x_bookmarks` descriptor SHALL resolve readiness through the live
`CredentialProvider`, never through `Settings`. It SHALL report `ready=false`
with code `credentials_missing` unless both `X_AUTH_TOKEN` and `X_CT0` are
present, `ready=false` with code `session_expired` while the current value of
either is recorded as rejected, `ready=false` with code `source_unavailable`
when the provider fails, and `ready=true` otherwise. Readiness output SHALL
never contain a credential value.

#### Scenario: One cookie is not a session

- **WHEN** only `X_AUTH_TOKEN` or only `X_CT0` is configured
- **THEN** the descriptor reports `ready=false` with code `credentials_missing`

#### Scenario: A rotated session recovers without restart

- **WHEN** either cookie is marked rejected and a new value for it is then patched into the OpenBao cache
- **THEN** readiness changes from `session_expired` to `ready=true` in the same process

### Requirement: X bookmarks ingestion fails closed until the adapter ships

Until the X bookmarks adapter exists, the `ingest_x_bookmarks` orchestrator
entry SHALL make no network call and persist nothing, and SHALL return an
`IngestionResponse` with `status=error` and one error with the stable code
`source_unavailable`, never raising. The durable ingestion operation SHALL
attach a result with that sanitized code and terminate as failed.

#### Scenario: Enabled source before the adapter

- **WHEN** an `x_bookmarks` command is executed by the canonical ingestion handler
- **THEN** the operation result has `status: error`, `items_ingested: 0`, no content IDs, and one `source_unavailable` error, and the operation fails
