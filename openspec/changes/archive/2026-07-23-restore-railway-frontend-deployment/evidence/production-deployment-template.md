# Production frontend deployment evidence

> Copy to `production-deployment.md` during implementation. Record only
> sanitized identifiers and status metadata. Never include credentials,
> cookies, authorization headers, raw environment variables, or request
> headers.

## Candidate and rollback manifest (capture before deployment)

- Candidate commit SHA:
- Candidate branch:
- GitHub `frontend-release` check URL:
- GitHub check conclusion and checked SHA:
- Working tree clean:
- Candidate pushed:
- Railway project ID:
- Railway environment ID:
- Railway frontend service ID:
- Public frontend URL:
- Active deployment ID before release:
- Active revision before release:
- Last successful deployment ID:
- Last successful revision:
- Rollback command:
- Abort criteria evaluated:

## Railway release

- Deployment start UTC:
- Deployment end UTC:
- Deployment ID:
- Deployed candidate revision:
- Release stamp path:
- Release stamp SHA-256:
- Served frontend revision:
- Served frontend revision source:
- Railway CLI release message:
- Uploaded lockfile observed:
- Railpack install command:
- Railpack Node version:
- Build status:
- Deployment status:
- Revision matches CI-passed candidate:

## Browser and network verification

- Verification window start UTC:
- Verification window end UTC:
- Browser/session attribution:
- Public route and load status:
- Capability request method/path:
- Capability response status:
- Capability source options rendered:
- Canary request method/path:
- Canary response status:
- Canary source kind:
- Sanitized canary marker:
- Visible form submission count:
- Durable operation ID:
- Durable operation terminal status:
- Client retries observed:
- Retention/cleanup disposition:

## Bounded backend-log correlation

- Backend service ID:
- Log query window:
- Capability request correlation:
- Canonical ingestion request correlation:
- `POST /api/v1/contents/ingest` count:
- `POST /api/v1/content/save-url` count:

## Outcome

- Acceptance outcomes passed:
- Rollback required:
- Rollback deployment ID:
- Notes:
