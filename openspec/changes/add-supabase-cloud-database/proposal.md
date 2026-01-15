# Change: Add Supabase Cloud Database Support

## Why

The current implementation only supports local PostgreSQL, which limits deployment options and creates barriers for users who want to quickly try the newsletter aggregator. By adding Supabase as a cloud database option:

1. **Lower barrier to entry**: Users can leverage Supabase's free tier (500MB) without managing database infrastructure
2. **Bring your own backend**: Each user connects their own Supabase instance, owning all their data (similar to [kbroose/stash](https://github.com/kbroose/stash))
3. **Zero infrastructure setup**: No need to run Docker Compose or install PostgreSQL locally
4. **Production-ready**: Supabase provides managed backups, connection pooling via Supavisor, and automatic SSL

## Single-User Model

This proposal follows the **Stash pattern**: each user brings their own Supabase project. This is the foundation for additional Supabase features (storage, sharing) in separate proposals.

## What Changes

- **NEW**: Database provider abstraction layer in `src/storage/providers/`
- **NEW**: Supabase-specific configuration with connection pooling support
- **NEW**: Environment variable detection for automatic provider selection
- **MODIFIED**: `src/storage/database.py` to use provider abstraction
- **MODIFIED**: `src/config/settings.py` to add Supabase configuration options
- **MODIFIED**: Documentation for Supabase setup instructions

## Configuration Examples

**Local PostgreSQL (unchanged)**:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/newsletters
```

**Supabase (bring your own)**:
```bash
# Option 1: Direct connection string
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Option 2: Component-based config (auto-constructs URL)
SUPABASE_PROJECT_REF=your-project-ref
SUPABASE_DB_PASSWORD=your-database-password
SUPABASE_REGION=us-east-1
SUPABASE_POOLER_MODE=transaction
```

## Impact

- **New spec**: `database-provider` - Database connection abstraction
- **Affected code**:
  - `src/storage/database.py` - Use provider factory
  - `src/config/settings.py` - Add Supabase settings
  - `src/storage/providers/` - New provider implementations
  - `docs/SETUP.md` - Supabase setup instructions
- **Migration**: None required (existing DATABASE_URL continues to work)

## Related Proposals

This is proposal 1 of 5 in the Supabase integration series:

1. **supabase-database** (this proposal) - Database provider abstraction
2. **supabase-storage** - Storage provider for audio/media files
3. **content-sharing** - Public share links for content
4. **content-capture** - Chrome extension and bookmarklet
5. **mobile-reader** - PWA and mobile-friendly templates

## Non-Goals

- Storage provider (separate proposal: `supabase-storage`)
- Content sharing (separate proposal: `content-sharing`)
- Chrome extension (separate proposal: `content-capture`)
- Mobile/PWA features (separate proposal: `mobile-reader`)
