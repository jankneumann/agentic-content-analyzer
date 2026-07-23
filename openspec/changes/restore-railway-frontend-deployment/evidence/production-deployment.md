# Production frontend deployment evidence

> Sanitized identifiers and status metadata only. No credentials, cookies,
> authorization headers, raw environment variables, or request headers.

## Candidate and rollback manifest (captured before deployment)

- Candidate commit SHA: 648e2c9b02646c6f101957ff4816847992ac919e
- Candidate branch: openspec/restore-railway-frontend-deployment
- GitHub `frontend-release` check URL: https://github.com/jankneumann/agentic-content-analyzer/actions/runs/30043506275/job/89328888655
- GitHub check conclusion and checked SHA: success; checked_sha=648e2c9b02646c6f101957ff4816847992ac919e
- Working tree clean: true
- Candidate pushed: true
- Railway project ID: 4b0db3b8-110d-4a13-81d5-440aa2ddc98d
- Railway environment ID: cd39a506-8d8f-4aa2-b298-766fde2b8dd8
- Railway frontend service ID: 00281b0e-9de9-414d-844e-da3ab02836f5
- Public frontend URL: https://app.aca.rotkohl.ai
- Active deployment ID before release: 6e246f86-e5a3-4146-8893-1e1a162055c8
- Active revision before release: 74f9a87e4205515ac3532c8461eab60dd3cf2098
- Last successful deployment ID: 6e246f86-e5a3-4146-8893-1e1a162055c8
- Last successful revision: 74f9a87e4205515ac3532c8461eab60dd3cf2098
- Rollback command: from a clean detached checkout of 19ef0ebfd9dc4f819a9e55ac4e645dfb13ec941b run railway up --ci --project 4b0db3b8-110d-4a13-81d5-440aa2ddc98d --environment cd39a506-8d8f-4aa2-b298-766fde2b8dd8 --service 00281b0e-9de9-414d-844e-da3ab02836f5 --message frontend-rollback-19ef0ebf
- Abort criteria evaluated: passed; active deployment and revision, public domain, exact target IDs, known-good rollback deployment 0d5201c0-b08d-4758-b70b-302e7237b6b2 at revision 19ef0ebfd9dc4f819a9e55ac4e645dfb13ec941b, and detached-revision rollback procedure confirmed before mutation

## Railway release

- Deployment start UTC: 2026-07-23T20:48:49Z
- Deployment end UTC: 2026-07-23T20:50:04Z
- Deployment ID: 253e84a9-7946-48c6-b24a-cde6ca73313d
- Deployed candidate revision: 648e2c9b02646c6f101957ff4816847992ac919e
- Railway CLI release message: frontend-release 648e2c9b02646c6f101957ff4816847992ac919e
- Uploaded lockfile observed: web/package-lock.json
- Railpack install command: npm ci
- Railpack Node version: 22.23.1
- Build status: SUCCESS
- Deployment status: SUCCESS
- Revision matches CI-passed candidate: true

## Browser and network verification

- Verification window start UTC: 2026-07-23T20:53:16Z
- Verification window end UTC: 2026-07-23T20:53:36Z
- Browser/session attribution: Headless Chromium 149 via repository Playwright; authenticated UI session used only the visible login and ingestion form; an earlier preflight timeout made no ingestion POST, and in-app browser runtime initialization had failed before navigation with Cannot redefine property process
- Public route and load status: GET https://app.aca.rotkohl.ai/ingest 200; authenticated ingestion route rendered
- Capability request method/path: GET /api/v1/capabilities
- Capability response status: 200
- Capability source options rendered: true; 18 capability-driven source options rendered, including URL
- Canary request method/path: POST /api/v1/ingestions
- Canary response status: 202
- Canary source kind: url
- Sanitized canary marker: aca-release-smoke=648e2c9b
- Visible form submission count: 1
- Durable operation ID: 104
- Durable operation terminal status: completed
- Client retries observed: 0
- Retention/cleanup disposition: retained as labeled release evidence; no supported content deletion path was used

## Bounded backend-log correlation

- Backend service ID: 46b135a6-d361-4985-947b-e27049f612a7
- Log query window: 2026-07-23T20:53:00Z/2026-07-23T20:54:55Z
- Capability request correlation: requestId c7S1JVUoS1ySTgO16WHkDg; GET /api/v1/capabilities; 200; 2026-07-23T20:53:19.835640244Z; HeadlessChrome/149
- Canonical ingestion request correlation: requestId g1VVmwquScyVTm4I9o6EoQ; POST /api/v1/ingestions; 202; durable operation 104; 2026-07-23T20:53:22.446127671Z; HeadlessChrome/149
- `POST /api/v1/contents/ingest` count: 0
- `POST /api/v1/content/save-url` count: 0

## Outcome

- Acceptance outcomes passed: true
- Rollback required: false
- Rollback deployment ID: 0d5201c0-b08d-4758-b70b-302e7237b6b2
- Notes: Preflight recaptured before candidate 648e2c9b. Deployment 09320189-62bc-432f-9641-d8b184bc4505 from candidate 6a785cef is excluded because the uploader omitted web/package-lock.json and used npm install. Deployment 6e246f86-e5a3-4146-8893-1e1a162055c8 from candidate 74f9a87e is excluded because implementation review found critically vulnerable protobufjs 8.0.0 in its npm production graph. Rollback remains pinned to known-good deployment 0d5201c0-b08d-4758-b70b-302e7237b6b2 at revision 19ef0ebfd9dc4f819a9e55ac4e645dfb13ec941b.
