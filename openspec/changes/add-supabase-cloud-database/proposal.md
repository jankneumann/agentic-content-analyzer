# Change: Add Supabase Cloud Database Support

## Why

The current implementation only supports local PostgreSQL, which limits deployment options and creates barriers for users who want to quickly try the newsletter aggregator. By adding Supabase as a cloud database option:

1. **Lower barrier to entry**: Users can leverage Supabase's free tier without managing database infrastructure
2. **Multi-user readiness**: Prepares the architecture for a "bring your own database" model where each user connects their own Supabase instance (similar to [kbroose/stash](https://github.com/kbroose/stash))
3. **Zero infrastructure setup**: No need to run Docker Compose or install PostgreSQL locally
4. **Production-ready**: Supabase provides managed backups, connection pooling via Supavisor, and automatic SSL

## What Changes

- **NEW**: Database provider abstraction layer in `src/storage/providers/`
- **NEW**: Supabase-specific configuration with connection pooling support
- **NEW**: Environment variable detection for automatic provider selection
- **MODIFIED**: `src/storage/database.py` to use provider abstraction
- **MODIFIED**: `src/config/settings.py` to add Supabase configuration options
- **MODIFIED**: Documentation for Supabase setup instructions

### Configuration Examples

**Local PostgreSQL (unchanged)**:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/newsletters
```

**Supabase**:
```bash
# Option 1: Direct connection string
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# Option 2: Supabase-specific config (auto-constructs URL)
SUPABASE_PROJECT_REF=your-project-ref
SUPABASE_DB_PASSWORD=your-database-password
SUPABASE_REGION=us-east-1
SUPABASE_POOLER_MODE=transaction  # or session
```

## Impact

- Affected specs: None (new capability)
- New spec: `database-provider` - Database connection abstraction
- Affected code:
  - `src/storage/database.py` - Use provider factory
  - `src/config/settings.py` - Add Supabase settings
  - `src/storage/providers/` - New provider implementations
  - `docs/SETUP.md` - Supabase setup instructions
- Migration: None required (existing DATABASE_URL continues to work)
