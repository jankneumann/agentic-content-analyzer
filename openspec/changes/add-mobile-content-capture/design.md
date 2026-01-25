# Design: Mobile Content Capture

## Context

iOS users cannot install browser extensions. Safari on iOS has no extension API for content capture. Users need a native-feeling way to save URLs from any app on their iPhone.

### Constraints
- iOS Share Sheet is the universal sharing mechanism
- Apple Shortcuts app can make HTTP requests
- PWA "Share Target" API has limited iOS Safari support
- Users may have Supabase OR Neon as their database backend

## Goals

1. One-tap URL capture from iOS Share Sheet
2. Works with both Supabase and Neon database backends
3. Minimal setup friction (no app install required)
4. Graceful offline handling

## Non-Goals

1. Native iOS app (too much maintenance burden)
2. Background sync daemon (iOS restrictions)
3. Full offline-first with local database
4. Push notifications for capture status

## Decisions

### Decision 1: iOS Shortcuts as Primary Capture Method

**What**: Provide a pre-built Apple Shortcut that users add to their device.

**Why**:
- Native iOS integration without App Store approval
- Appears in Share Sheet for all apps
- Can make HTTP requests directly
- Supports input prompts for tags/notes
- Free to distribute

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| Native iOS App | Best UX | Requires App Store, Swift expertise |
| PWA Share Target | Web-based | Safari support incomplete |
| Bookmarklet | Universal | Clunky on mobile Safari |
| Shortcuts | Native feel, no app | Limited error handling |

**Shortcut Flow**:
```
1. Receive shared URL from Share Sheet
2. (Optional) Prompt for tags/notes
3. POST to /api/v1/content/save-url
4. Show success/error notification
```

### Decision 2: Lightweight API Key Authentication

**What**: Optional bearer token authentication for the save-url endpoint.

**Why**:
- Mobile clients can't use session cookies reliably
- Full OAuth is overkill for personal use
- API keys are simple to configure in Shortcuts
- Can be disabled for local/trusted networks

**Implementation**:
```python
# Optional API key header
Authorization: Bearer <api_key>

# Or query parameter (for bookmarklets)
?api_key=<key>

# If no auth configured, endpoint is open (existing behavior)
```

**Key Storage**:
- Store hashed API keys in database
- Associate with user (when auth system exists) or as standalone
- Rate limit per key: 60 requests/minute default

### Decision 3: Database-Agnostic Design

**What**: The capture API works identically with Supabase, Neon, or local PostgreSQL.

**Why**: The existing `DatabaseProvider` abstraction handles all connection differences.

**Flow**:
```
Save URL API
     ↓
get_db() → Provider Factory
     ↓
Detects provider from config:
  - DATABASE_PROVIDER=supabase → SupabaseProvider
  - DATABASE_PROVIDER=neon → NeonProvider
  - DATABASE_PROVIDER=local → LocalProvider
     ↓
Returns configured SQLAlchemy Session
     ↓
ContentService.create() - same code for all providers
```

**Provider Differences** (handled automatically):
| Provider | SSL | Pooling | Cold Start |
|----------|-----|---------|------------|
| Local | No | Standard | None |
| Supabase | Required | Supavisor | None |
| Neon | Required | -pooler suffix | 2-5s possible |

### Decision 4: Background Content Extraction

**What**: Return immediately after creating Content record, extract in background.

**Why**:
- Mobile users expect instant feedback
- Content extraction can take 5-30 seconds
- Neon cold starts add latency
- Background tasks are already used for ingestion

**API Response**:
```python
# Immediate response (< 500ms)
{
    "content_id": 12345,
    "status": "queued",
    "message": "URL saved. Content extraction in progress."
}
```

**Background Processing**:
```python
@router.post("/api/v1/content/save-url")
async def save_url(request: SaveURLRequest, background_tasks: BackgroundTasks):
    # 1. Validate URL
    # 2. Check for duplicates (by URL or content hash)
    # 3. Create Content with status=PENDING
    # 4. Queue background extraction
    background_tasks.add_task(extract_and_parse_url, content.id)
    # 5. Return immediately
    return {"content_id": content.id, "status": "queued"}
```

### Decision 5: Mobile-Optimized Web Save Page

**What**: A simple HTML page at `/save` that works as bookmarklet target and fallback.

**Why**:
- Bookmarklets redirect here with URL params
- Works on any mobile browser
- Fallback if Shortcut doesn't work
- Can show save status/history

**URL Pattern**:
```
GET /save?url=https://...&title=...&excerpt=...
```

**Design Requirements**:
- Touch targets ≥ 44x44 pixels
- Single-column layout
- Large, readable text (16px minimum)
- Clear success/error states
- Optional: recent saves list

## API Endpoints

### Save URL (Enhanced)

```python
POST /api/v1/content/save-url
Headers:
  Authorization: Bearer <api_key>  # Optional
  Content-Type: application/json

Body:
{
    "url": "https://example.com/article",      # Required
    "title": "Article Title",                   # Optional (extracted if missing)
    "excerpt": "Selected text from page",       # Optional
    "tags": ["ai", "research"],                 # Optional
    "notes": "User's notes about the content",  # Optional
    "source": "ios_shortcut"                    # Optional (for analytics)
}

Response (201 Created):
{
    "content_id": 12345,
    "status": "queued",
    "message": "URL saved. Content extraction in progress.",
    "duplicate": false
}

Response (200 OK - Duplicate):
{
    "content_id": 12340,
    "status": "exists",
    "message": "URL already saved.",
    "duplicate": true
}

Response (429 Too Many Requests):
{
    "error": "rate_limit_exceeded",
    "message": "Too many requests. Try again in 60 seconds.",
    "retry_after": 60
}
```

### Check Status

```python
GET /api/v1/content/{id}/status
Headers:
  Authorization: Bearer <api_key>  # Optional

Response:
{
    "content_id": 12345,
    "status": "parsed",           # pending, parsing, parsed, failed
    "title": "Extracted Title",
    "word_count": 1500,
    "error": null
}
```

### Web Save Page

```python
GET /save
Query Params:
  url: string (required)
  title: string (optional)
  excerpt: string (optional)

Response: HTML page with save form
```

## File Structure

```
src/
├── api/
│   ├── save_routes.py           # Save URL endpoint (enhanced)
│   └── auth/
│       └── api_keys.py          # Simple API key auth
├── services/
│   └── url_extractor.py         # Content extraction service
└── templates/
    └── save.html                # Mobile-optimized save page

shortcuts/
├── Save to Newsletter.shortcut  # iOS Shortcut file
└── README.md                    # Installation instructions

docs/
└── MOBILE_CAPTURE.md            # User guide
```

## iOS Shortcut Specification

The Shortcut will:

1. **Receive Input**: Accept URL from Share Sheet
2. **Get API Config**: Read saved API URL and key from Shortcut input fields
3. **Optional Prompt**: Ask for tags/notes (can be skipped)
4. **Make Request**: POST to save-url endpoint
5. **Handle Response**: Show success notification or error alert
6. **Return**: Close and return to source app

**Shortcut Actions** (simplified):
```
1. Receive [URLs] from Share Sheet
2. Set Variable [url] to [Shortcut Input]
3. Text: {"url": "[url]", "source": "ios_shortcut"}
4. Get Contents of URL
   - URL: [API_URL]/api/v1/content/save-url
   - Method: POST
   - Headers: Authorization: Bearer [API_KEY]
   - Request Body: [Text from step 3]
5. If [Status Code] is 201 or 200
   - Show Notification "Saved!"
6. Otherwise
   - Show Alert "Save failed: [Response]"
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Neon cold start delays | Show "Connecting..." in Shortcut; async extraction |
| iOS Shortcuts complexity | Provide pre-built, tested Shortcut file |
| API key exposure on device | Keys are user-generated, can be rotated |
| Rate limiting false positives | Generous limits (60/min), clear error messages |
| Content extraction failures | Store URL even if extraction fails; retry option |

## Testing Plan

1. **Unit Tests**: API endpoint with mock database
2. **Integration Tests**: Full flow with both Supabase and Neon
3. **iOS Testing**: Manual testing on iPhone with Shortcut
4. **Load Testing**: Verify rate limiting works correctly
