# knowledge-base Specification Delta

## ADDED Requirements

### Requirement: HTTP knowledge base search endpoint

The system SHALL expose a `GET /api/v1/kb/search` endpoint that performs full-text and semantic search across compiled knowledge base topics. Search results MUST include topic slug, title, score, and a short excerpt. The endpoint SHALL require `X-Admin-Key` authentication.

#### Scenario: Search with matching query returns topics

- **WHEN** a client sends `GET /api/v1/kb/search?q=transformer&limit=10` with a valid `X-Admin-Key`
- **THEN** the API returns a 200 response with a JSON array of matching topics
- **AND** each topic includes `slug`, `title`, `score`, `excerpt`, and `last_compiled_at`

#### Scenario: Search with no matches returns empty array

- **WHEN** a client searches for a term that matches no compiled topic
- **THEN** the API returns a 200 response with an empty `topics` array
- **AND** the response includes `total_count: 0`

#### Scenario: Unauthenticated search is rejected in production

- **WHEN** a client calls `GET /api/v1/kb/search` in production without `X-Admin-Key`
- **THEN** the API returns a 401 Unauthorized response

#### Scenario: Search honors limit parameter

- **WHEN** a client requests `GET /api/v1/kb/search?q=ai&limit=5`
- **THEN** the response contains at most 5 topics
- **AND** `total_count` reflects the full match count (which may exceed `limit`)

### Requirement: HTTP KB lint endpoints (read and fix)

The system SHALL expose `GET /api/v1/kb/lint` (read-only health check) and `POST /api/v1/kb/lint/fix` (apply auto-corrections). The GET variant reports staleness, orphans, and score anomalies without modifying data. The POST variant applies fixes and returns a diff report.

The lint categories use these quantitative definitions:

- **stale**: topic whose `last_compiled_at` is older than 30 days (configurable via `KB_LINT_STALE_DAYS` env var).
- **orphaned**: topic with zero inbound content references AND zero outbound graph relationships (i.e., both reference-count=0 and graph-degree=0).
- **score_anomaly**: topic whose latest relevance/coherence score deviates by more than 3σ from the mean of all topics in the same category (rolling 30-day window); requires minimum sample size of 10 topics in the category to emit — below that, the category is skipped rather than flagged spuriously.

#### Scenario: GET lint returns health report without changes

- **WHEN** a client calls `GET /api/v1/kb/lint` with a valid admin key
- **THEN** the API returns a 200 response with `stale_topics`, `orphaned_topics`, and `score_anomalies` arrays
- **AND** each array is populated using the quantitative definitions above
- **AND** no database mutations occur

#### Scenario: POST lint/fix applies corrections and returns diff

- **WHEN** a client calls `POST /api/v1/kb/lint/fix` with a valid admin key
- **THEN** the API applies the auto-fixable corrections
- **AND** returns a 200 response with a `corrections_applied` array listing each fix
- **AND** the operation is recorded in the audit log with operation=`kb.lint.fix`

#### Scenario: POST lint/fix when no corrections are needed

- **WHEN** `POST /api/v1/kb/lint/fix` runs with no fixable issues
- **THEN** the API returns 200 with `corrections_applied: []`
- **AND** the audit log records the attempt with zero-diff notes
