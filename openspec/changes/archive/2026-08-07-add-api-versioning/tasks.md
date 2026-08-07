# Implementation Tasks

## 1. Version Configuration

- [ ] 1.1 Create `src/api/versioning.py`
- [ ] 1.2 Define `VersionStatus` enum (ACTIVE, DEPRECATED, SUNSET)
- [ ] 1.3 Create `API_VERSIONS` configuration dict
- [ ] 1.4 Add helper functions:
  - `get_version_status(version: str) -> VersionStatus`
  - `get_sunset_date(version: str) -> date | None`
  - `get_successor(version: str) -> str | None`

## 2. Deprecation Middleware

- [ ] 2.1 Create deprecation middleware in `src/api/versioning.py`
- [ ] 2.2 Add `Deprecation` header (RFC 8594)
- [ ] 2.3 Add `Sunset` header with date
- [ ] 2.4 Add `Link` header with successor URL
- [ ] 2.5 Add `X-API-Version` header
- [ ] 2.6 Add `X-API-Status` header

## 3. Reorganize Routes

- [ ] 3.1 Create `src/api/v1/` directory
- [ ] 3.2 Create `src/api/v1/__init__.py` with v1 router
- [ ] 3.3 Move content routes to `src/api/v1/contents.py`
- [ ] 3.4 Move summary routes to `src/api/v1/summaries.py`
- [ ] 3.5 Move digest routes to `src/api/v1/digests.py`
- [ ] 3.6 Update imports in moved files
- [ ] 3.7 Update `src/api/app.py` to mount v1 router

## 4. Sunset Handler

- [ ] 4.1 Create sunset handler function
- [ ] 4.2 Return 410 Gone status
- [ ] 4.3 Include migration guide URL in response
- [ ] 4.4 Include successor version in response

## 5. OpenAPI Documentation

- [ ] 5.1 Update OpenAPI schema to show version
- [ ] 5.2 Add deprecation notices to deprecated endpoints
- [ ] 5.3 Configure separate OpenAPI docs per version (optional)
- [ ] 5.4 Add version info to API description

## 6. Version Detection

- [ ] 6.1 Add version extraction from request path
- [ ] 6.2 Add version to request state for logging
- [ ] 6.3 Include version in observability spans (if enabled)

## 7. Testing

- [ ] 7.1 Test deprecation headers are present
- [ ] 7.2 Test sunset behavior returns 410
- [ ] 7.3 Test version detection
- [ ] 7.4 Verify existing endpoints work after reorganization

## 8. Documentation

- [ ] 8.1 Create `docs/api/versioning.md`
- [ ] 8.2 Document version lifecycle
- [ ] 8.3 Document when to create new versions
- [ ] 8.4 Create migration guide template
- [ ] 8.5 Update API documentation with version info

## 9. Future: v2 Preparation (Not Now)

When breaking changes are needed:
- [ ] 9.1 Create `src/api/v2/` directory
- [ ] 9.2 Implement changed endpoints
- [ ] 9.3 Update `API_VERSIONS` to deprecate v1
- [ ] 9.4 Create migration guide
- [ ] 9.5 Announce deprecation timeline
