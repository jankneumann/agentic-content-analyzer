# cli-interface Spec Delta

## ADDED Requirements

### Requirement: Job History CLI Command

The system SHALL provide `aca jobs history` as a CLI command for viewing historical job executions with filtering.

#### Scenario: List recent job history
- **WHEN** `aca jobs history` is executed without flags
- **THEN** the 20 most recent jobs are displayed in a Rich table
- **AND** the table columns are: Date/Time, Task, Content ID, Job ID, Content Title, Status
- **AND** the Task column shows human-readable labels (e.g., "Summarize" instead of "summarize_content")

#### Scenario: Filter by time range
- **WHEN** `aca jobs history --since 1d` is executed
- **THEN** only jobs from the last 24 hours are shown
- **AND** supported values include `1d`, `7d`, `30d`

#### Scenario: Limit number of entries
- **WHEN** `aca jobs history --last 50` is executed
- **THEN** the 50 most recent jobs are shown regardless of time range

#### Scenario: Filter by task type
- **WHEN** `aca jobs history --type summarize` is executed
- **THEN** only jobs matching the `summarize_content` entrypoint are shown
- **AND** `--type` accepts human-readable aliases: `summarize`, `batch`, `extract`, `scan`, `process`, `ingest`
- **AND** aliases are mapped to entrypoints via `TYPE_ALIASES` in `src/models/jobs.py`

#### Scenario: Filter by status
- **WHEN** `aca jobs history --status failed` is executed
- **THEN** only jobs with `failed` status are shown

#### Scenario: Combined filters
- **WHEN** `aca jobs history --since 7d --status completed --type summarize` is executed
- **THEN** only jobs matching ALL filters are shown

#### Scenario: JSON output mode
- **WHEN** `aca --json jobs history` is executed (global `--json` flag)
- **THEN** output is valid JSON with `jobs`, `total`, `offset`, `limit` fields
- **AND** each job includes `id`, `entrypoint`, `task_label`, `status`, `content_id`, `content_title`, `created_at`

#### Scenario: No matching jobs
- **WHEN** `aca jobs history --since 1d --type summarize` is executed
- **AND** no jobs match the criteria
- **THEN** a message "No jobs found matching the criteria." is displayed
- **AND** exit code is 0
