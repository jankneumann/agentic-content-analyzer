# job-management Spec Delta

## ADDED Requirements

### Requirement: Job History API with Content Enrichment

The system SHALL provide an API endpoint for querying historical job records enriched with content metadata for audit purposes.

#### Scenario: List job history with descriptions
- **WHEN** `GET /api/v1/jobs/history` is called
- **THEN** a 200 OK response is returned with JSON:
```json
{
  "data": [
    {
      "id": 123,
      "entrypoint": "summarize_content",
      "task_label": "Summarize",
      "status": "completed",
      "content_id": 42,
      "description": "AI Newsletter #15 - GPT-5 Launch",
      "error": null,
      "created_at": "ISO8601",
      "started_at": "ISO8601",
      "completed_at": "ISO8601"
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 150}
}
```
- **AND** `task_label` is a human-readable name derived from `entrypoint`
- **AND** `description` is a context-aware text resolved from job payload: content title (via LEFT JOIN) for content-linked jobs, source name for ingestion jobs, batch count for batch jobs, or `null` if no context available
- **AND** jobs without a `content_id` in their payload have `content_id: null` and `description` derived from other payload fields (e.g., "Gmail ingestion" for ingest jobs)

#### Scenario: Filter history by time range shorthand
- **WHEN** `GET /api/v1/jobs/history?since=1d` is called
- **THEN** only jobs created within the last 24 hours are returned
- **AND** supported shorthands are `1d`, `7d`, `30d`

#### Scenario: Filter history by ISO datetime
- **WHEN** `GET /api/v1/jobs/history?since=2025-01-15T00:00:00Z` is called
- **THEN** only jobs created on or after that timestamp are returned

#### Scenario: Filter history by task type
- **WHEN** `GET /api/v1/jobs/history?entrypoint=summarize_content` is called
- **THEN** only jobs with that entrypoint are returned

#### Scenario: Filter history by status
- **WHEN** `GET /api/v1/jobs/history?status=failed` is called
- **THEN** only jobs with that status are returned

#### Scenario: Combined filters
- **WHEN** `GET /api/v1/jobs/history?since=7d&status=completed&entrypoint=summarize_content` is called
- **THEN** only jobs matching ALL filters are returned

#### Scenario: Pagination
- **WHEN** `GET /api/v1/jobs/history?page=2&page_size=50` is called
- **THEN** the second page of 50 results is returned
- **AND** default page_size is 20, max is 100

#### Scenario: Invalid since parameter
- **WHEN** `GET /api/v1/jobs/history?since=invalid` is called
- **AND** `since` is not a valid ISO 8601 datetime or shorthand (`1d`, `7d`, `30d`)
- **THEN** a 400 Bad Request response is returned
- **AND** the error message indicates the supported formats

#### Scenario: Empty result set
- **WHEN** `GET /api/v1/jobs/history?since=1d&entrypoint=summarize_content` is called
- **AND** no jobs match the filter criteria
- **THEN** a 200 OK response is returned with `"data": []` and `"pagination": {"total": 0}`

#### Scenario: Jobs without content_id in payload
- **WHEN** the history includes jobs with entrypoint `ingest_content`
- **AND** these jobs do not have `content_id` in their payload
- **THEN** the response includes these jobs with `content_id: null`
- **AND** `description` is derived from the payload `source` field (e.g., "Gmail ingestion", "RSS ingestion")

### Requirement: Entrypoint Label Mapping

The system SHALL maintain a mapping from job entrypoint names to human-readable task labels.

#### Scenario: Known entrypoints have labels
- **WHEN** a job with entrypoint `summarize_content` is included in a history response
- **THEN** `task_label` SHALL be `"Summarize"`

#### Scenario: Unknown entrypoints use entrypoint as label
- **WHEN** a job has an entrypoint not in the label mapping
- **THEN** `task_label` SHALL be the raw entrypoint value (e.g., `"my_custom_task"`)

### Requirement: Task History Web UI

The system SHALL provide a web page at `/task-history` under the Management navigation group showing historical job executions in a filterable table.

#### Scenario: Table displays job history
- **WHEN** a user navigates to `/task-history`
- **THEN** a table is displayed with columns: Date/Time, Task, Content ID, Job ID, Description, Status
- **AND** rows are ordered by date/time descending (newest first)

#### Scenario: Filter by task type
- **WHEN** a user selects a task type from the filter dropdown
- **THEN** the table re-fetches data with the `entrypoint` query parameter
- **AND** all visible rows display the selected task type in the Task column

#### Scenario: Filter by status
- **WHEN** a user selects a status from the filter dropdown
- **THEN** the table re-fetches data with the `status` query parameter
- **AND** all visible rows display the selected status in the Status column

#### Scenario: Filter by time range
- **WHEN** a user selects "Last 24 hours" from the time range selector
- **THEN** the table re-fetches data with `since=1d` query parameter

#### Scenario: Pagination
- **WHEN** there are more results than fit on one page
- **THEN** pagination controls are displayed showing current page and total pages
- **AND** clicking "Next" increments the page parameter and fetches new data

#### Scenario: Empty state
- **WHEN** the query returns zero results (no jobs or all filtered out)
- **THEN** a centered message "No task history found" is displayed instead of the table
- **AND** if filters are active, the message suggests clearing filters

#### Scenario: Navigation entry
- **WHEN** a user views the sidebar navigation
- **THEN** "Task History" appears under the Management group
- **AND** clicking it navigates to `/task-history`
