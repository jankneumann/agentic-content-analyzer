# Change: Refactor Database Provider Selection to Explicit Configuration

## Why

The current database provider detection uses a priority cascade that causes confusion when multiple providers are partially configured:

```
1. Explicit DATABASE_PROVIDER (if set)
2. SUPABASE_PROJECT_REF present → Supabase
3. NEON_PROJECT_ID present → Neon
4. URL contains .supabase. → Supabase
5. URL contains .neon.tech → Neon
6. Default → Local
```

**Problem**: A user with `DATABASE_URL=...neon.tech` but leftover `SUPABASE_PROJECT_REF` in their `.env` gets Supabase selected instead of Neon. This is unintuitive and hard to debug.

**Solution**: Make `DATABASE_PROVIDER` the single source of truth with startup validation, removing the implicit detection magic.

## What Changes

### Configuration Model
- `DATABASE_PROVIDER` becomes the authoritative selector (default: `"local"`)
- Remove implicit provider detection from env vars (`SUPABASE_PROJECT_REF`, `NEON_PROJECT_ID`)
- Keep URL pattern detection only as a validation hint (warn if URL doesn't match provider)

### Startup Validation
- Fail fast if `DATABASE_PROVIDER=neon` but URL doesn't contain `.neon.tech`
- Fail fast if `DATABASE_PROVIDER=supabase` but no Supabase config present
- Warn if URL pattern suggests a different provider than configured

### Simplified Settings
- Remove `get_database_provider()` method (replaced by direct `database_provider` field)
- `get_effective_database_url()` uses match statement on explicit provider
- `get_migration_database_url()` same simplification

## Impact

- **Affected specs**: `database-provider`
- **Affected code**: `src/config/settings.py`, `src/storage/providers/factory.py`
- **Breaking**: Users must add `DATABASE_PROVIDER=neon|supabase|local` to `.env`
- **Migration**: Clear error message guides users to set the variable

## Related Proposals

- `add-neon-provider` (completed) - Added Neon to detection chain
- `add-supabase-cloud-database` (pending) - Added Supabase to detection chain
