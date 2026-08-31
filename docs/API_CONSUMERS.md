# Independently deployed API consumers

Inventory of HTTP/MCP clients that are not always shipped in lockstep with this
repository. Used before any breaking `/api/v1` change (issue #492).

ADR-0002 (`openspec/changes/archive/2026-08-07-add-api-versioning/`) deferred a
speculative global `/api/v2`. The July 2026 unified-workflow cutover replaced
mutation shapes **in place** under `/api/v1` with contract `info.version: 2.0.0`.
Independently installed clients were not given an adapter. The next incompatible
change MUST be a URL-major (`/api/v2`) with a documented window; do not silently
reshape `/api/v1` again.

Canonical Python models use `additionalProperties: false` (`StrictModel`).
Response widening that adds required fields, or request bodies that send unknown
fields, breaks older `WorkflowApiClient` builds.

## Compatibility policy

| Consumer | Update mechanism | Oldest supported contract | Window |
|----------|------------------|---------------------------|--------|
| Web frontend (`web/`) | Deployed with backend (`aca-app`) | Current `openspec/contracts/content-workflows/` | Lockstep with API |
| CLI (`aca`) | Same git revision as the API when using `--wait` HTTP mode | Current generated `src/contracts/workflow_models.py` | Lockstep; no older CLI is supported against a newer API |
| MCP server in this repo | Same process / same revision | Current OpenAPI + MCP tool schemas | Lockstep |
| Chrome extension (`extension/`) | Manual unpacked install from this repo | Current `POST /api/v1/ingestions` `kind=url` | No window; reinstall from `main` |
| iOS Shortcut | Manual Shortcuts.app edit; **not** auto-updated | Current shortcut page (`kind: url` + `X-Admin-Key`) | **None** |
| Bookmarklet | Re-drag from `/api/v1/content/bookmarklet` | Current bookmarklet/save page | **None** |
| Web save page | Served by the API | Current `/api/v1/content/save` | Lockstep with API |
| agentic-assistant HTTP tools | Assistant checkout + `CONTENT_ANALYZER_URL` OpenAPI discovery | `operationId` `search` and `knowledge_graph` (#421) | No window; assistant must rediscover `/openapi.json` |
| agentic-assistant MCP | Assistant MCP client pointed at this server | Current MCP tool contracts | No window |

"No window" means a client that still speaks a retired shape is unsupported. Do
not restore `/api/v1/content/save-url` or a compatibility adapter.

## Capture contract (URL)

- Method/path: `POST /api/v1/ingestions`
- Auth: `X-Admin-Key: <ADMIN_API_KEY>`
- Body: `{ "kind": "url", "url": "<https URL>", "title"?, "tags"?, "notes"?, "routing_mode"?, "force_reprocess"? }`
- Success: `202` `OperationHandle` (`schema_version: 2`, `operation_id`, `status_url`)
- Status: `GET /api/v1/operations/{operation_id}`
- Retired: `POST /api/v1/content/save-url`, `POST /api/v1/content/save-page`

Executable checks: `tests/unit/test_capture_consumer_contracts.py` (Pydantic
rejects legacy bodies; live in-repo clients must instruct `kind: url` and may
name retired paths only as 404/do-not-use). There is no supported old-client
fixture because no compatibility window is offered.

## agentic-assistant evidence

ACA-side lockstep for the teacher-role preferred tools:

- `GET /api/v1/kb/search` `operationId=search`
- `POST /api/v1/graph/query` `operationId=knowledge_graph`
- Regression: `tests/unit/test_http_tool_operation_ids.py` (issue #421, commit `a7405eef`)

This repository does not contain the assistant checkout. Remaining consumer-side
work is to point `CONTENT_ANALYZER_URL` at a current ACA instance and run
`uv run assistant --list-tools` until both `content_analyzer:search` and
`content_analyzer:knowledge_graph` bind. MCP callers must use the current tool
schemas; there is no recorded lockstep SHA in this repo.

## Next breaking change

Open a focused URL-major OpenSpec proposal (`/api/v2`) before any incompatible
request/response change. In-place `/api/v1` reshape is how independently
installed Shortcuts were stranded.