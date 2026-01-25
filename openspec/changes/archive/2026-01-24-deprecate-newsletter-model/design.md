# Design: Newsletter Deprecation Strategy

## Context

The Newsletter model was the original data model for ingested content. The Content model was introduced as a unified replacement supporting multiple source types. Both currently coexist, creating:

- **Dual maintenance burden**: Changes must be applied to both models
- **Confusion**: Developers unsure which model to use
- **Data inconsistency risk**: Newsletter and Content can drift out of sync
- **Technical debt**: 29+ files still import Newsletter

### Stakeholders
- **Developers**: Need clear guidance on which model to use
- **API consumers**: Need migration path for Newsletter endpoints
- **Frontend users**: Need seamless transition between views

## Goals / Non-Goals

### Goals
- Provide clear, phased deprecation path
- Zero data loss during migration
- Minimal disruption to existing workflows
- Clear communication of deprecation timeline

### Non-Goals
- Immediate removal (too risky)
- Maintaining long-term backwards compatibility (adds complexity)
- Migrating external integrations (out of scope)

## Decisions

### Decision 1: Phased Deprecation Over Big-Bang Removal

**Choice**: 4-phase deprecation over 4-6 weeks

**Rationale**:
- Allows gradual discovery of hidden dependencies
- Provides time for external integrations to migrate
- Reduces risk of production incidents
- Enables rollback at each phase

**Alternatives considered**:
- Big-bang removal: Too risky, could break unknown integrations
- Keep both indefinitely: Increases maintenance burden
- Automatic migration layer: Over-engineered for our scale

### Decision 2: Soft Deprecation First

**Choice**: Start with UI/UX deprecation signals before code removal

**Rationale**:
- Users learn about Content model naturally
- Deprecation warnings surface in IDE/logs
- Builds confidence before breaking changes

**Implementation**:
```typescript
// TypeScript deprecation
/** @deprecated Use Content type instead. Will be removed in v2.0 */
export interface Newsletter { ... }
```

```python
# Python deprecation
import warnings

class Newsletter(Base):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Newsletter is deprecated. Use Content model instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)
```

### Decision 3: Type Aliases for Gradual Migration

**Choice**: Convert Newsletter types to aliases pointing to Content

**Rationale**:
- Existing code continues to work
- TypeScript compiler catches type mismatches
- Easy grep for remaining Newsletter usage

**Implementation**:
```typescript
// Phase 3: newsletter.ts becomes aliases
/** @deprecated Use Content directly */
export type Newsletter = Content;
/** @deprecated Use ContentSource directly */
export type NewsletterSource = ContentSource;
```

### Decision 4: API Deprecation Headers

**Choice**: Use standard HTTP deprecation headers before removal

**Rationale**:
- Industry standard approach (RFC 8594)
- API clients can detect and warn automatically
- Provides clear sunset date

**Implementation**:
```python
@router.get("/newsletters")
async def list_newsletters(...):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 01 Mar 2025 00:00:00 GMT"
    response.headers["Link"] = '</api/v1/contents>; rel="successor-version"'
```

### Decision 5: Database Table Retention

**Choice**: Keep `newsletters` table for 30 days after Phase 4

**Rationale**:
- Allows emergency rollback
- Provides audit trail
- Minimal storage cost

**Implementation**:
- Phase 4.3.2: Rename table to `newsletters_archived` instead of drop
- Phase 4+30d: Create separate cleanup migration to drop archived table

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hidden Newsletter dependencies | Medium | Comprehensive grep before each phase; monitoring |
| External API consumers break | High | Deprecation headers; 4-week sunset period |
| Data inconsistency during migration | Medium | Phase 2 removes dual-write atomically |
| Rollback needed after Phase 4 | High | Keep archived table 30 days; verified backups |

## Migration Plan

### Timeline

| Phase | Duration | Start Condition |
|-------|----------|-----------------|
| Phase 1 | 1 week | Immediate |
| Phase 2 | 1-2 weeks | T0 complete |
| Phase 3 | 1 week | Phase 2 deployed |
| Phase 4 | 1 day + 30d retention | 2 weeks zero Newsletter usage |

### Monitoring

Track these metrics during migration:
- Newsletter API endpoint calls (should trend to zero)
- Newsletter model instantiations (via deprecation warning logs)
- `/newsletters` page views (should trend to zero)
- Error rates on Content endpoints (should remain stable)

### Rollback Triggers

Initiate rollback if:
- Error rate increases >5% on affected endpoints
- Critical bug discovered in Content model
- External integration reports breaking issue

## Open Questions

1. **Rename `NewsletterSummary` to `ContentSummary`?**
   - Pro: Consistent naming
   - Con: Large diff, many references
   - Recommendation: Defer to separate proposal

2. **Keep Newsletter API indefinitely as alias?**
   - Pro: Zero breaking changes
   - Con: Maintenance burden
   - Recommendation: No, clean removal after sunset period

3. **Migrate Newsletter-specific fields (e.g., `sender_email`)?**
   - Already handled: Content has `author` and `metadata_json`
   - No additional migration needed
