-- Deterministic contract fixtures used by provenance and operation tests.
-- IDs are intentionally high to avoid collisions with ordinary test seeds.

INSERT INTO contents (
    id, source_type, source_id, title, markdown_content, raw_content, content_hash,
    canonical_id, status, published_date, ingested_at
) VALUES
    (990001, 'rss', 'contract-rss-1', 'Canonical RSS item', '# Canonical body', 'Canonical body',
     'contract-rss-canonical', NULL, 'completed',
     '2026-07-12T10:00:00Z', '2026-07-12T10:01:00Z'),
    (990002, 'gmail', 'contract-gmail-alias-1', 'Duplicate Gmail alias', '', NULL,
     'contract-rss-canonical', 990001, 'completed',
     '2026-07-12T10:00:00Z', '2026-07-12T10:02:00Z'),
    (990003, 'readwise', 'contract-readwise-1', 'Null publication date', '# Readwise body', 'Readwise body',
     'contract-readwise-null-date', NULL, 'completed',
     NULL, '2026-07-12T11:00:00Z');

-- Summary columns vary across migrations; the implementation fixture builder
-- must create persisted summaries for 990001 and 990003 using the live model.
-- It must deliberately leave 990002 without an independent summary.

INSERT INTO pgqueuer_jobs (
    id, entrypoint, payload, priority, status, created_at, execute_after,
    idempotency_key, retry_count
) VALUES (
    990001,
    'create_digest',
    '{
      "schema_version": 2,
      "operation_type": "digest.create",
      "input": {
        "digest_type": "daily",
        "period_start": "2026-07-12T00:00:00Z",
        "period_end": "2026-07-13T00:00:00Z"
      },
      "progress": 0,
      "message": "Queued",
      "cancel_requested": false,
      "resource": null,
      "result": null
    }'::jsonb,
    0,
    'queued',
    '2026-07-13T00:00:00Z',
    '2026-07-13T00:00:00Z',
    'contract:digest:2026-07-12',
    0
);
