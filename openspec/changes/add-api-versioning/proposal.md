# Change: Add API Versioning

## Why

As the API evolves, breaking changes are inevitable:
- Model restructuring (like the unified Content model)
- Field renames or type changes
- Endpoint deprecation and removal

Without versioning:
- Clients break on updates
- No migration path for consumers
- Difficult to maintain backward compatibility

By adding API versioning:

1. **Safe evolution**: Introduce breaking changes in new versions
2. **Migration window**: Clients can migrate at their pace
3. **Clear contracts**: Each version has defined behavior
4. **Deprecation path**: Old versions sunset gracefully

## Current State

The `refactor-unified-content-model` proposal is ~75% complete with migrations already run in production. The `/api/v1/newsletters` endpoints are marked deprecated but still functional. This proposal formalizes the versioning approach for **future changes**.

## Versioning Strategy

### URL-Based Versioning
```
/api/v1/contents     ← Current stable
/api/v2/contents     ← Future breaking changes
```

**Why URL-based**:
- Explicit and visible
- Easy to route in reverse proxies
- Clear in API documentation
- No header parsing needed

### Version Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Active    │───▶│ Deprecated  │───▶│   Sunset    │
│             │    │ (6 months)  │    │  (removed)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

- **Active**: Current recommended version
- **Deprecated**: Works but returns warning headers
- **Sunset**: Returns 410 Gone with migration guide link

## What Changes

### Router Structure
- **MODIFIED**: `src/api/` reorganized by version
  ```
  src/api/
  ├── v1/
  │   ├── __init__.py
  │   ├── contents.py
  │   ├── summaries.py
  │   └── digests.py
  ├── v2/           # Created when needed
  └── app.py        # Mounts versioned routers
  ```

### Deprecation Headers
- **NEW**: Middleware to add deprecation headers
  ```
  Deprecation: true
  Sunset: Sat, 01 Jan 2028 00:00:00 GMT
  Link: </api/v2/contents>; rel="successor-version"
  ```

### Version Detection
- **NEW**: Version detection in middleware
- **NEW**: Request logging includes API version

### Documentation
- **MODIFIED**: OpenAPI spec per version
- **NEW**: Migration guides in docs

## Configuration

```python
# src/api/versioning.py
API_VERSIONS = {
    "v1": {
        "status": "deprecated",  # or "active", "sunset"
        "sunset_date": "2028-01-01",
        "successor": "v2",
    },
    "v2": {
        "status": "active",
        "sunset_date": None,
        "successor": None,
    },
}
```

## Impact

- **New spec**: `api-versioning` - Version management
- **New code**:
  - `src/api/versioning.py` - Version config and middleware
  - `src/api/v1/` - Reorganized v1 routes
- **Modified**:
  - `src/api/app.py` - Mount versioned routers
  - API documentation
- **No new dependencies**

## Related Proposals

- **refactor-unified-content-model**: Newsletter deprecation uses this pattern
- **add-api-security-hardening**: Auth applies across versions
- **add-observability**: Track usage by API version

## When to Create v2

Create a new version when:
- Removing or renaming fields
- Changing response structure
- Removing endpoints
- Changing authentication

Don't create new version for:
- Adding new optional fields
- Adding new endpoints
- Performance improvements
- Bug fixes

## Non-Goals

- Header-based versioning (Accept header)
- Query parameter versioning (?version=2)
- GraphQL (different paradigm)
- Automatic version negotiation
