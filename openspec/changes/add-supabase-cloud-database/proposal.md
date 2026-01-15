# Change: Add Supabase Cloud Database and Storage Support

## Why

The current implementation only supports local PostgreSQL and local file storage, which limits deployment options and creates barriers for users who want a mobile-ready experience. By adding Supabase as a cloud platform option:

1. **Lower barrier to entry**: Users can leverage Supabase's free tier (500MB database, 1GB storage) without managing infrastructure
2. **Bring your own backend**: Each user connects their own Supabase instance, owning all their data (similar to [kbroose/stash](https://github.com/kbroose/stash))
3. **Mobile-ready from day one**: Cloud-hosted database and storage enable access from any device
4. **Shareable content**: Users can generate public links to share specific articles and audio with others
5. **Zero infrastructure setup**: No need to run Docker Compose, PostgreSQL, or configure S3

## Single-User Model

This proposal follows the **Stash pattern**: each user brings their own Supabase project. This dramatically simplifies the architecture:

| Concern | What We DON'T Need | What We DO Need |
|---------|-------------------|-----------------|
| Authentication | Supabase Auth, JWT handling | User's anon key in config |
| Data isolation | RLS policies, user_id columns | Nothing - user owns all data |
| Sharing | Complex permissions | Public flags + share tokens |

## What Changes

### Database Provider (Core)
- **NEW**: Database provider abstraction layer in `src/storage/providers/`
- **NEW**: Supabase-specific configuration with connection pooling support
- **MODIFIED**: `src/storage/database.py` to use provider abstraction
- **MODIFIED**: `src/config/settings.py` for Supabase configuration

### Storage Provider (Audio/Media)
- **NEW**: Storage provider abstraction in `src/storage/file_providers/`
- **NEW**: Supabase Storage provider for cloud file hosting
- **NEW**: Local and S3 providers for flexibility
- **MODIFIED**: Podcast generation to use storage abstraction
- **MODIFIED**: Audio URLs served via signed URLs or public bucket

### Content Sharing
- **NEW**: `is_public` and `share_token` fields on Content, Summary, Digest models
- **NEW**: `/shared/{token}` public endpoint for viewing shared content
- **NEW**: Share button in web UI to generate shareable links

### Chrome Extension / Bookmarklet
- **NEW**: Minimal Chrome extension for one-click content saving
- **NEW**: Universal bookmarklet as fallback
- **NEW**: API endpoint `POST /api/v1/content/save-url` for extension

## Configuration Examples

**Local Development (unchanged)**:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/newsletters
STORAGE_PROVIDER=local
STORAGE_PATH=data/uploads
```

**Supabase (bring your own)**:
```bash
# Database
SUPABASE_PROJECT_REF=your-project-ref
SUPABASE_DB_PASSWORD=your-database-password
SUPABASE_REGION=us-east-1

# Storage
STORAGE_PROVIDER=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=eyJ...  # From Supabase dashboard

# Optional: Override specific settings
SUPABASE_POOLER_MODE=transaction
SUPABASE_STORAGE_BUCKET=audio-files
```

## Impact

- **New specs**:
  - `database-provider` - Database connection abstraction
  - `storage-provider` - File storage abstraction
  - `content-sharing` - Public sharing mechanism
- **Affected code**:
  - `src/storage/` - Provider abstractions
  - `src/config/settings.py` - Supabase and storage settings
  - `src/models/` - Add sharing fields
  - `src/api/` - Public sharing endpoints
  - `src/tts/` - Use storage provider for audio
  - `docs/` - Setup and deployment guides
- **New components**:
  - `extension/` - Chrome extension for content saving
  - `bookmarklet/` - Universal bookmarklet
- **Migration**: Alembic migration for sharing fields (backward compatible)

## Non-Goals

- **Multi-tenant authentication**: Each user runs their own instance
- **User management UI**: No admin interface for managing users
- **Real-time sync**: Standard request/response model (real-time can be added later)
- **Edge Functions**: Keep processing in Python API (Edge Functions are TypeScript/Deno)
