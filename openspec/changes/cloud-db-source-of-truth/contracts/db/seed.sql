-- Seed rows for contract tests against audit_log.
-- Covers: read endpoint (no operation), audited destructive endpoint, failed request.

INSERT INTO audit_log (timestamp, request_id, method, path, operation, admin_key_fp, status_code, body_size, client_ip, notes) VALUES
    ('2026-04-21T10:00:00Z', 'req-test-001', 'GET',  '/api/v1/kb/search',            NULL,                       'a1b2c3d4', 200,   0,    '127.0.0.1', '{}'::jsonb),
    ('2026-04-21T10:01:00Z', 'req-test-002', 'POST', '/api/v1/graph/extract-entities', 'graph.extract_entities', 'a1b2c3d4', 200,   32,   '127.0.0.1', '{"content_id": 42}'::jsonb),
    ('2026-04-21T10:02:00Z', 'req-test-003', 'POST', '/api/v1/references/resolve',   'references.resolve',       'a1b2c3d4', 200,   2,    '127.0.0.1', '{}'::jsonb),
    ('2026-04-21T10:03:00Z', 'req-test-004', 'POST', '/api/v1/kb/lint/fix',          'kb.lint.fix',              'a1b2c3d4', 500,   2,    '127.0.0.1', '{"error": "db_connection_lost"}'::jsonb),
    ('2026-04-21T10:04:00Z', 'req-test-005', 'GET',  '/api/v1/audit',                NULL,                       'zzzzzzzz', 401,   0,    '10.0.0.99', '{}'::jsonb)
;
