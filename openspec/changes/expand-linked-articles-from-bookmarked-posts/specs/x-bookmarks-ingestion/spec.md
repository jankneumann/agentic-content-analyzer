## ADDED Requirements

### Requirement: X bookmark rows reference their linked articles

Every X bookmark row written in an ingestion run (inserted, or rewritten under
`force_reprocess`) SHALL get one `content_reference` per distinct http(s) link
of the post and its quoted post that is neither an X self link (x.com,
twitter.com, t.co) nor an X media link (`*.twimg.com`), whether or not
`expand_links` is enabled. arXiv, DOI and Semantic Scholar links SHALL be stored
as identifier references and other links as URL-only references. The references
SHALL be committed together with the row, and a failure to store them SHALL keep
the row and add a `persistence_error` warning. No inline reference hook and no
legacy queue job SHALL run.

#### Scenario: Reference recorded with expansion off

- **WHEN** a bookmark carrying one external article link is ingested with `expand_links` false
- **THEN** the bookmark row has one unresolved URL-only `content_reference` to the article and no url operation is submitted

#### Scenario: Reference failure keeps the bookmark

- **WHEN** storing a written bookmark's references fails
- **THEN** the bookmark row is committed without references and the run succeeds with a `persistence_error` warning

### Requirement: Linked articles are submitted as canonical url operations

When `expand_links` resolves to true, the system SHALL submit one canonical
`url` ingestion operation through `OperationService` for each distinct article
link of the rows written in the run, with tags `["x-bookmark"]` and a note naming
the bookmarked post URL, keyed per URL so a link shared by several bookmarks or
submitted again while its operation is active does not queue a second
operation. It SHALL NOT submit X self links, X media links, non-http(s) links,
feed or YouTube playlist URLs, or URLs already stored as content, and SHALL NOT
expand rows that were only known or linked to an existing row. The ingestion
thread SHALL submit through the operation service lent by the canonical
ingestion handler and SHALL NOT execute the url ingestion inline. Submissions
per run SHALL be bounded by `x_bookmarks_max_expanded_links` (default 50).

#### Scenario: One external link

- **WHEN** a bookmark carrying one external link is ingested with `expand_links` true
- **THEN** exactly one url operation is submitted for that link and a `content_reference` links the post row to it

#### Scenario: Shared link and rerun

- **WHEN** two bookmarks in one run link the same article, and the run is repeated with no new bookmarks
- **THEN** one url operation is submitted in the first run and none in the second

#### Scenario: Media and self links

- **WHEN** a bookmark links only to `pbs.twimg.com`, `video.twimg.com`, or x.com URLs
- **THEN** no url operation is submitted

#### Scenario: Per-run cap

- **WHEN** a run's written bookmarks carry more distinct article links than `x_bookmarks_max_expanded_links`
- **THEN** only that many url operations are submitted and the run warns `link_expansion_capped`

### Requirement: Link expansion failures never fail the bookmark run

A failed url operation submission SHALL NOT fail the X bookmarks ingestion: the
bookmark rows and their references SHALL stay stored, no further links SHALL be
submitted in that run, and the result SHALL carry a `link_expansion_failed`
warning with counts only (no URL). The codes `link_expansion_capped` and
`link_expansion_failed` SHALL be admitted by the result sanitizer, the workflow
alert diagnostic code list, and the alert envelope schema, and the durable
result details SHALL expose `references_recorded`, `links_submitted`, and
`links_skipped`.

#### Scenario: Queue unavailable

- **WHEN** submitting a url operation raises during an X bookmarks run
- **THEN** the run status is `ok`, the rows are stored, and the result warns `link_expansion_failed`

#### Scenario: Run outside the worker

- **WHEN** the X bookmarks ingestion runs with `expand_links` true outside a canonical ingestion handler
- **THEN** nothing is ingested inline and the result warns `link_expansion_failed`
