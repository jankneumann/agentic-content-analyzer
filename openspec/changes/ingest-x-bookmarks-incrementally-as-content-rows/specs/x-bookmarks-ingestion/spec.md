## ADDED Requirements

### Requirement: Incremental X bookmarks sync

The X bookmarks adapter SHALL walk the operator's bookmarks newest-first and
SHALL stop after the first page whose every post is already stored as a
bookmark, meaning a row with `source_id` `xpost:<post id>` of source type
`x_bookmarks` or any row with that `source_id` whose `metadata_json` carries
`bookmarked: true`. With `full` set it SHALL walk every page up to the client's
page cap. `max_items` SHALL cap the rows a run writes and SHALL default to the
enabled source's `max_entries`. A post repeated across pages SHALL be written
once.

#### Scenario: A two-page walk ingests every bookmark once

- **WHEN** the adapter runs for the first time against a timeline of several pages
- **THEN** it reads every page and writes exactly one `x_bookmarks` row per bookmarked post

#### Scenario: Unchanged bookmarks read one page

- **WHEN** the adapter runs again and no bookmark was added
- **THEN** it fetches exactly one page and writes zero rows

#### Scenario: New bookmarks on top

- **WHEN** posts were bookmarked since the last run
- **THEN** the walk stops at the first page that is entirely known and only the new posts are written

#### Scenario: Full walk

- **WHEN** the adapter runs with `full` set against stored bookmarks
- **THEN** it fetches every page and writes no duplicate row

### Requirement: X bookmarks fail closed and report partial walks

The adapter SHALL read every page before writing any row. When the X session
is missing or rejected on any page it SHALL write no row and SHALL return
`status=error` with code `credentials_missing` or `session_expired`, and the
durable ingestion result SHALL carry `command_key` `x_bookmarks`. When X
rate-limits the walk, the page cap is reached, or `max_items` is reached before
the walk caught up, the adapter SHALL write the posts it read and SHALL add a
`rate_limited`, `page_cap_reached`, or `item_cap_reached` warning. A rate limit
before the first page SHALL be an error. These codes SHALL belong to the closed
ingestion diagnostic vocabulary and to the workflow alert diagnostic codes in
both the model and the alert envelope schema.

#### Scenario: Expired session writes nothing

- **WHEN** X rejects the session on the first or a later page
- **THEN** no Content row is written and the result is `status=error` with code `session_expired`

#### Scenario: Rate limit mid-walk keeps the pages read

- **WHEN** X rate-limits the walk after the first page for longer than the client waits
- **THEN** the first page's posts are written and the result carries a `rate_limited` warning

### Requirement: X bookmarks backfill resumes interrupted walks

When a walk ends before reaching the oldest bookmark because of a rate limit,
the page cap, `max_items`, or an upstream failure, the adapter SHALL save the
position where the unread bookmarks start as the settings override
`x_bookmarks.backfill_cursor`. Each incremental run SHALL first walk from the
newest bookmark with the known-page stop and then, when that walk caught up and
item and page budget remain, SHALL continue from the saved cursor without the
known-page stop, saving the new position or clearing the cursor when it reaches
the oldest bookmark. A position left by the head walk SHALL replace the saved
one. A `full` run SHALL ignore the cursor and reset it from its own outcome. A
run that fails closed on credentials SHALL NOT change the cursor.

#### Scenario: A capped first run is continued by later runs

- **WHEN** the first run is capped by `max_items` and later runs use the same cap
- **THEN** each later run reads the known head page, then ingests the next older batch from the saved cursor, and the run that reaches the oldest bookmark clears the cursor

#### Scenario: A rate-limited walk is completed by the next run

- **WHEN** X rate-limits a walk after its first page and the next run is not limited
- **THEN** the next run catches up on the head and ingests the bookmarks the first run did not read

#### Scenario: Full resets the cursor

- **WHEN** a `full` run reads to the oldest bookmark while a cursor is saved
- **THEN** the walk starts at the newest bookmark and the cursor is cleared

### Requirement: X bookmark document shape

Each bookmarked post SHALL become one Content row with `source_type`
`x_bookmarks`, `source_id` `xpost:<post id>`, the canonical `x.com` post URL,
the Grok search title form `@handle: <first 120 characters>`, the author
handle, and `published_date` equal to the post's creation time. Its markdown
SHALL be rendered by the same thread-to-markdown function as the Grok search
adapter, with a quoted post rendered as its own section. `links_json` SHALL
hold the outbound URLs of the post and its quoted post, and `metadata_json`
SHALL hold the Grok search X post keys plus the quoted post summary and
`bookmarked: true`. Sharing the renderer SHALL NOT change Grok search output.

#### Scenario: A bookmark renders like a Grok search post

- **WHEN** a bookmarked post with a link, a photo, and a quoted post is ingested
- **THEN** its markdown equals the shared renderer's output for that post, contains a quoted post section, and its metadata carries `bookmarked: true`

#### Scenario: Grok search output is unchanged

- **WHEN** Grok search converts a thread after the renderer was shared
- **THEN** its title, content hash, and metadata keys equal the values produced before the change

### Requirement: X posts are stored once across sources

The adapter SHALL NOT insert a second row for a post whose `xpost:<post id>`
already exists under another source type. It SHALL set `bookmarked: true` in
that row's `metadata_json` instead, and later walks SHALL treat the post as
known. The Grok search adapter SHALL skip a post whose `xpost:<post id>`
exists under any source type and, when forced to reprocess, SHALL reset such a
row to `pending` in place instead of inserting a second row.

#### Scenario: A Grok search row is flagged, not duplicated

- **WHEN** a bookmarked post was already stored by Grok search
- **THEN** no `x_bookmarks` row is inserted for it and the existing row carries `bookmarked: true`

#### Scenario: Grok search surfaces a bookmarked post

- **WHEN** Grok search returns a post already stored as a bookmark
- **THEN** it skips the post and no second row exists for that `source_id`

#### Scenario: Grok search force-reprocesses a bookmarked post

- **WHEN** Grok search runs with `force_reprocess` and returns a post stored as a bookmark
- **THEN** the bookmark row is reset to `pending` with its content unchanged and no `xsearch` row is inserted

### Requirement: X bookmarks run through the canonical hooks and durable result

`ingest_x_bookmarks` SHALL run under the post-persist ingestion filter hook
like every orchestrator ingest function, SHALL store each written row's
outbound links in `links_json` without running an inline reference hook or
enqueueing a legacy job, and SHALL report one configured-source outcome for the
enabled source's public key so the durable result does not count the source as
omitted. `expand_links=None` SHALL resolve to the enabled source's
`expand_links`. `force_reprocess` SHALL reset walked `x_bookmarks` rows to
`pending` in place.

#### Scenario: Durable ingestion of bookmarks

- **WHEN** an `x_bookmarks` ingestion operation runs through the workflow handler registry and `IngestionService` with a configured source snapshot
- **THEN** the result lists the written rows in `content_ids`, `source_outcomes` holds the source's public key, and `source_outcomes_omitted` is 0

#### Scenario: Outbound links are kept for reference recording

- **WHEN** a bookmarked post links to an external article
- **THEN** the row's `links_json` holds that URL and no inline reference hook or legacy queue job runs
