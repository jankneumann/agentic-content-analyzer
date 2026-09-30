## ADDED Requirements

### Requirement: Bookmark link references carry an expansion state

Each content reference recorded for an X bookmark row SHALL carry an expansion state of `pending`, `submitted`, `skipped`, or `failed` and an attempt count; references recorded for other sources SHALL have no expansion state. A feed or playlist link, which expansion never submits, SHALL start `skipped`.

#### Scenario: New bookmark reference starts pending
- **WHEN** a bookmark row is written with an outbound article link
- **THEN** its reference has expansion state `pending` and zero attempts, unless the run submits it

#### Scenario: Other sources are untouched
- **WHEN** a reference is stored for a newsletter row
- **THEN** its expansion state is empty

### Requirement: Expansion retries stored references from the leftover budget

Every expand-links run SHALL, after expanding newly written posts, submit older `pending` or `failed` bookmark links, oldest first, until the run's link budget is spent. A link SHALL NOT be attempted after three failed submissions, and a link already stored as content SHALL be marked `skipped` instead of submitted.

#### Scenario: Capped link is submitted later
- **WHEN** a run is capped before a link and a later expand-links run has budget left
- **THEN** the later run submits that link and marks its references `submitted`

#### Scenario: Attempt limit
- **WHEN** a link's submission has failed three times
- **THEN** no later run submits it

#### Scenario: Shared link
- **WHEN** two bookmarks reference the same link
- **THEN** it is submitted once and both references record the outcome

### Requirement: Retry-only bookmark runs

`XBookmarksIngestCommand.retry_links` SHALL run only the retry pass with the full link budget: it SHALL NOT fetch any bookmark page, SHALL NOT need an X session, and SHALL NOT move the backfill cursor.

#### Scenario: Retry without an X session
- **WHEN** the operator runs `aca ingest x-bookmarks --retry-links` with no X session configured
- **THEN** pending links are submitted, no X request is made, and the run does not fail with `credentials_missing`
