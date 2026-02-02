# Design: Content Capture

## Context

Users want to save web content while browsing. We need simple tools that work across browsers and integrate with the existing content pipeline.

## Goals

1. Provide Chrome extension for one-click saving
2. Provide universal bookmarklet as fallback
3. Extract and process content from URLs
4. Integrate with existing Content model

## Non-Goals

1. Firefox/Safari native extensions (bookmarklet works everywhere)
2. Full-page screenshots
3. Offline content capture
4. Browser sync

## Decisions

### Decision 1: Minimal Chrome Extension

**What**: Simple Manifest V3 extension with popup UI.

**Why**: Easy to develop, maintain, and load unpacked. No Chrome Web Store approval needed initially.

```
extension/
├── manifest.json       # Manifest V3
├── popup.html          # Save UI
├── popup.js            # Save logic
├── options.html        # Configuration
├── options.js          # Config storage
└── icons/              # Extension icons
```

### Decision 2: API Key Authentication

**What**: Use Supabase anon key or custom API key for authentication.

**Why**: Simple, no OAuth flow needed. User configures once.

```javascript
// Extension saves to user's instance
fetch(`${config.apiUrl}/api/v1/content/save-url`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${config.apiKey}`
  },
  body: JSON.stringify({ url, title, excerpt })
});
```

### Decision 3: Bookmarklet Fallback

**What**: JavaScript bookmarklet that opens save page with URL params.

**Why**: Works on any browser including mobile Safari.

```javascript
javascript:(function(){
  var u=encodeURIComponent(location.href);
  var t=encodeURIComponent(document.title);
  var s=encodeURIComponent(window.getSelection().toString().slice(0,500));
  window.open('https://YOUR_APP/api/v1/content/save?url='+u+'&title='+t+'&excerpt='+s);
})();
```

### Decision 4: Background Content Extraction

**What**: Queue URL for async processing, return immediately.

**Why**: Content extraction can be slow. Don't block the extension UI.

```python
@router.post("/api/v1/content/save-url")
async def save_url(request: SaveURLRequest, background_tasks: BackgroundTasks):
    # Check for duplicates
    existing = get_content_by_url(request.url)
    if existing:
        return {"content_id": existing.id, "status": "duplicate"}

    # Create pending content record
    content = create_content(
        source_type=ContentSource.WEBPAGE,
        source_url=request.url,
        title=request.title,
        status=ContentStatus.PENDING
    )

    # Queue extraction
    background_tasks.add_task(extract_url_content, content.id)

    return {"content_id": content.id, "status": "queued"}
```

### Decision 5: URL Content Extraction

**What**: Use existing parsers (MarkItDown, Readability) for extraction.

```python
async def extract_url_content(content_id: int):
    content = get_content(content_id)

    # Fetch page
    response = await httpx.get(content.source_url)

    # Extract with MarkItDown or Readability
    result = parser_router.parse(response.content, "text/html")

    # Update content record
    content.markdown_content = result.markdown
    content.status = ContentStatus.PARSED
    save_content(content)
```

## API Endpoints

```python
# Save URL (from extension/bookmarklet)
POST /api/v1/content/save-url
Body: { "url": "https://...", "title": "...", "excerpt": "..." }
Response: { "content_id": 123, "status": "queued" }

# Check status
GET /api/v1/content/{id}/status
Response: { "status": "parsed", "title": "..." }

# Web save page (for bookmarklet)
GET /api/v1/content/save?url=...&title=...&excerpt=...
Response: HTML page with save form
```

## File Structure

```
extension/
├── manifest.json
├── popup.html
├── popup.js
├── options.html
├── options.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md

bookmarklet/
└── bookmarklet.js

src/
├── api/
│   └── save_routes.py       # Save URL endpoint
├── services/
│   └── url_extractor.py     # Content extraction
└── templates/
    └── save.html            # Bookmarklet save page
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| CORS issues | Configure CORS for extension origin |
| Extraction failures | Graceful fallback to title/URL only |
| Rate limiting on target sites | Respect robots.txt, add delays |
