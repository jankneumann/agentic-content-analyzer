# Design: API Versioning

## Context

APIs evolve over time. Breaking changes are sometimes necessary (field renames, type changes, endpoint removal). Without versioning, clients break unexpectedly.

The `refactor-unified-content-model` proposal already uses deprecation headers for the Newsletter API. This proposal formalizes the versioning approach for future changes.

## Goals

1. Support multiple API versions simultaneously
2. Provide clear deprecation timeline
3. Enable gradual client migration
4. Document version lifecycle

## Non-Goals

1. Automatic version negotiation
2. Header-based versioning
3. GraphQL (different paradigm)

## Decisions

### Decision 1: URL-Based Versioning

**What**: Version in URL path: `/api/v1/`, `/api/v2/`.

**Why**:
- Explicit and visible
- Easy to route
- Clear in documentation
- No header parsing

```
/api/v1/contents     ← Current
/api/v2/contents     ← Future breaking changes
```

### Decision 2: Router Organization

**What**: Organize routes by version in separate modules.

```python
# src/api/v1/__init__.py
from fastapi import APIRouter
from .contents import router as contents_router
from .summaries import router as summaries_router

router = APIRouter(prefix="/api/v1")
router.include_router(contents_router)
router.include_router(summaries_router)

# src/api/app.py
from src.api.v1 import router as v1_router
from src.api.v2 import router as v2_router  # When needed

app.include_router(v1_router)
app.include_router(v2_router)
```

### Decision 3: Version Lifecycle

**What**: Three-stage lifecycle with defined timelines.

```
Active (current) → Deprecated (6 months) → Sunset (removed)
```

| Stage | Behavior |
|-------|----------|
| Active | Fully supported, documented as recommended |
| Deprecated | Works but returns warning headers |
| Sunset | Returns 410 Gone with migration guide link |

### Decision 4: Deprecation Headers

**What**: Standard deprecation headers from RFC 8594.

```python
# Middleware adds headers for deprecated versions
Deprecation: true
Sunset: Sat, 01 Jan 2028 00:00:00 GMT
Link: </api/v2/contents>; rel="successor-version"
X-API-Version: v1
X-API-Status: deprecated
```

### Decision 5: Version Configuration

**What**: Centralized version configuration.

```python
# src/api/versioning.py
from datetime import date
from enum import Enum

class VersionStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"

API_VERSIONS = {
    "v1": {
        "status": VersionStatus.ACTIVE,
        "sunset_date": None,
        "successor": None,
        "introduced": date(2024, 1, 1),
    },
    # When v2 is created:
    # "v1": {
    #     "status": VersionStatus.DEPRECATED,
    #     "sunset_date": date(2028, 1, 1),
    #     "successor": "v2",
    # },
    # "v2": {
    #     "status": VersionStatus.ACTIVE,
    #     "sunset_date": None,
    #     "successor": None,
    # },
}
```

### Decision 6: Sunset Behavior

**What**: Return 410 Gone for sunset versions.

```python
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def sunset_handler(path: str):
    return JSONResponse(
        status_code=410,
        content={
            "error": "API_VERSION_SUNSET",
            "message": "This API version is no longer available",
            "migration_guide": "https://docs.example.com/api/migration/v1-to-v2",
            "successor_version": "/api/v2"
        }
    )
```

### Decision 7: When to Create New Version

**Create v2 when**:
- Removing fields from responses
- Renaming fields
- Changing field types
- Removing endpoints
- Changing authentication

**Don't create new version for**:
- Adding optional fields
- Adding new endpoints
- Performance improvements
- Bug fixes

## File Structure

```
src/api/
├── versioning.py           # Version config, middleware
├── v1/
│   ├── __init__.py         # v1 router
│   ├── contents.py
│   ├── summaries.py
│   ├── digests.py
│   └── health.py           # Version-independent
├── v2/                     # Created when needed
│   ├── __init__.py
│   └── ...
└── app.py                  # Mounts versioned routers
```

## Migration Path Example

When creating v2:

1. Create `src/api/v2/` with new endpoints
2. Update `API_VERSIONS` to deprecate v1
3. Add deprecation headers to v1 middleware
4. Document migration in `docs/api/migration-v1-v2.md`
5. After sunset date, replace v1 router with sunset handler

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Client confusion | Clear documentation, long deprecation window |
| Maintenance burden | Share code between versions where possible |
| Missed deprecation notices | Include in API response body too |
