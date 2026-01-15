# Design: Supabase Cloud Database and Storage Support

## Context

The newsletter aggregator currently requires local PostgreSQL via Docker Compose and stores audio files locally. This creates friction for users who want:
- Mobile access to summaries and digests
- Shareable links to content and audio
- Zero infrastructure setup

We want to support Supabase as a cloud alternative following the **single-user "bring your own backend"** pattern from [kbroose/stash](https://github.com/kbroose/stash).

## Goals

1. Support Supabase as a first-class database option
2. Support Supabase Storage for audio/media files
3. Enable content sharing via public links
4. Provide Chrome extension/bookmarklet for content capture
5. Maintain 100% backward compatibility with local setup

## Non-Goals

1. Multi-tenant authentication (each user runs their own instance)
2. User management UI
3. Real-time sync features
4. Edge Functions (keep processing in Python)
5. Supporting other cloud databases (RDS, Cloud SQL) in this change

---

## Part 1: Database Provider

### Decision 1: Provider Abstraction Pattern

**What**: Create a `DatabaseProvider` protocol with implementations for each provider.

**Why**: Allows provider-specific configuration without polluting the core database module. Follows the same pattern as `DocumentParser`.

```python
# src/storage/providers/base.py
class DatabaseProvider(Protocol):
    @property
    def name(self) -> str: ...
    def get_engine_url(self) -> str: ...
    def get_engine_options(self) -> dict[str, Any]: ...
    def health_check(self, engine: Engine) -> bool: ...
```

### Decision 2: Automatic Provider Detection

**Detection Order**:
1. Explicit `DATABASE_PROVIDER` env var
2. `SUPABASE_PROJECT_REF` present → Supabase
3. `DATABASE_URL` contains `.supabase.` → Supabase
4. Default → Local PostgreSQL

### Decision 3: Supabase Connection Pooling

Support both transaction mode (port 6543) and session mode (port 5432):

```python
engine_options = {
    "pool_pre_ping": True,
    "pool_size": 5,  # Limited for free tier
    "pool_recycle": 300,
    "connect_args": {
        "sslmode": "require",
        "options": "-c statement_timeout=30000",
    }
}
```

---

## Part 2: Storage Provider

### Decision 4: Storage Provider Abstraction

**What**: Create a `StorageProvider` protocol for file storage operations.

**Why**: Decouple audio/media storage from specific backends. Support local, Supabase Storage, and S3.

```python
# src/storage/file_providers/base.py
class StorageProvider(Protocol):
    @property
    def name(self) -> str: ...

    def upload(
        self,
        path: str,
        data: bytes,
        content_type: str,
        public: bool = False
    ) -> str:
        """Upload file, return URL."""
        ...

    def get_url(self, path: str, expires_in: int | None = None) -> str:
        """Get URL for file. If expires_in is None, return permanent URL."""
        ...

    def delete(self, path: str) -> bool:
        """Delete file."""
        ...

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        ...
```

### Decision 5: Provider Implementations

**LocalStorageProvider**:
- Stores files in configured directory (default: `data/uploads/`)
- URLs served via FastAPI static files or dedicated endpoint
- Suitable for development and self-hosted deployments

**SupabaseStorageProvider**:
- Uses `supabase-py` SDK for storage operations
- Supports public buckets (shareable) and private buckets (signed URLs)
- Free tier: 1GB storage, 2GB bandwidth/month

**S3StorageProvider** (optional, future):
- Standard boto3 implementation
- For users who prefer AWS

### Decision 6: Storage Configuration

```python
# src/config/settings.py additions
storage_provider: Literal["local", "supabase", "s3"] = "local"
storage_path: str = "data/uploads"  # For local
storage_bucket: str = "audio-files"  # For Supabase/S3

# Supabase Storage requires these (also used for API access)
supabase_url: str | None = None
supabase_anon_key: str | None = None
```

### Decision 7: Audio File Workflow

Current flow:
```
TTS Generation → Local file → Local path in database
```

New flow:
```
TTS Generation → Storage Provider → URL in database
                     ↓
           Local: /api/files/{path}
           Supabase: https://xxx.supabase.co/storage/v1/object/public/audio/...
           S3: https://bucket.s3.region.amazonaws.com/...
```

---

## Part 3: Content Sharing

### Decision 8: Share Token Approach

**What**: Add `is_public` flag and `share_token` to shareable models.

**Why**: Simple, no auth needed for shared content. Token-based "unlisted" sharing like YouTube.

```python
# Added to Content, NewsletterSummary, Digest models
is_public: bool = False
share_token: str | None = None  # UUID4, generated on first share
```

**URL Structure**:
```
/shared/content/{share_token}   → View content
/shared/summary/{share_token}   → View summary
/shared/digest/{share_token}    → View digest
/shared/audio/{share_token}     → Stream audio (redirect to storage URL)
```

### Decision 9: Share API Endpoints

```python
# Generate/get share link
POST /api/v1/content/{id}/share → {"share_url": "https://app/shared/content/abc123"}

# Revoke sharing
DELETE /api/v1/content/{id}/share → {"status": "unshared"}

# Public endpoints (no auth)
GET /shared/content/{token} → HTML page or JSON
GET /shared/audio/{token} → Redirect to audio URL
```

### Decision 10: Shared Content Rendering

For web access, shared content renders as:
- Mobile-friendly HTML page
- Open Graph meta tags for social sharing
- Audio player embed if audio exists
- "Powered by Newsletter Aggregator" footer with link

---

## Part 4: Chrome Extension / Bookmarklet

### Decision 11: Minimal Chrome Extension

**What**: Simple extension that captures page URL and optional selection.

**Why**: Stash's extension is proven to work. Keep it simple.

**Features**:
- One-click save current page
- Optional: highlight text to save with excerpt
- Configuration: user's API URL and anon key

```javascript
// Extension popup saves to user's instance
fetch(`${config.apiUrl}/api/v1/content/save-url`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Supabase-Anon-Key': config.anonKey
  },
  body: JSON.stringify({
    url: tab.url,
    title: tab.title,
    excerpt: selectedText
  })
});
```

### Decision 12: Bookmarklet Fallback

**What**: JavaScript bookmarklet for browsers without extension support.

**Why**: Works on mobile Safari, Firefox, any browser.

```javascript
javascript:(function(){
  var url=encodeURIComponent(location.href);
  var title=encodeURIComponent(document.title);
  window.open('https://YOUR_APP/save?url='+url+'&title='+title);
})();
```

### Decision 13: Save URL API Endpoint

```python
# POST /api/v1/content/save-url
class SaveURLRequest(BaseModel):
    url: HttpUrl
    title: str | None = None
    excerpt: str | None = None

# Flow:
# 1. Validate URL
# 2. Check for duplicates (by URL)
# 3. Queue content extraction (Readability/MarkItDown)
# 4. Return content ID for status polling
```

---

## File Structure

```
src/storage/
├── providers/                    # Database providers
│   ├── __init__.py
│   ├── base.py                   # DatabaseProvider protocol
│   ├── local.py                  # LocalPostgresProvider
│   ├── supabase.py               # SupabaseProvider
│   └── factory.py                # get_database_provider()
├── file_providers/               # Storage providers
│   ├── __init__.py
│   ├── base.py                   # StorageProvider protocol
│   ├── local.py                  # LocalStorageProvider
│   ├── supabase_storage.py       # SupabaseStorageProvider
│   └── factory.py                # get_storage_provider()
└── database.py                   # Uses database provider

src/api/
├── shared_routes.py              # Public /shared/* endpoints
└── content_routes.py             # Add /share and /save-url endpoints

extension/
├── manifest.json
├── popup.html
├── popup.js
├── config.js                     # User's API URL and key
└── icons/

bookmarklet/
└── bookmarklet.js                # Generated bookmarklet code
```

---

## Alternatives Considered

### Alternative A: Supabase Auth for Sharing
Use Supabase Auth with anonymous users for shared content.

**Rejected**: Adds complexity. Token-based sharing is simpler and proven.

### Alternative B: Supabase Edge Functions for Extension
Process saved URLs via Edge Function.

**Rejected**: Would require TypeScript/Deno. Keep processing in Python API.

### Alternative C: Full PWA with Offline Support
Add service worker, offline database sync.

**Rejected**: Over-engineering for MVP. Can add later if needed.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Supabase free tier limits (500MB DB, 1GB storage) | Document limits, recommend upgrade for heavy use |
| Share tokens could be enumerated | Use UUID4 (128-bit), rate limit `/shared/*` |
| Extension store approval delays | Provide "load unpacked" instructions, bookmarklet fallback |
| Storage provider abstraction overhead | Keep interface minimal, lazy provider init |

---

## Migration Plan

### Phase 1: Database Provider (Non-Breaking)
1. Create provider abstraction
2. Refactor database.py
3. Existing DATABASE_URL works unchanged

### Phase 2: Storage Provider
1. Create storage abstraction
2. Update TTS generation to use provider
3. Add migration for audio_url field updates

### Phase 3: Sharing
1. Add sharing fields to models
2. Create Alembic migration
3. Add share API endpoints
4. Create shared content pages

### Phase 4: Extension/Bookmarklet
1. Create Chrome extension
2. Create bookmarklet generator
3. Add save-url endpoint
4. Document setup

### Rollback
Each phase is independent. Can rollback any phase without affecting others.
