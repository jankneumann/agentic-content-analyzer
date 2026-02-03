# Content Capture Guide

Save web content to your Newsletter Aggregator while browsing. Two capture methods are available:

| Method | Best For | Browser Support |
|--------|----------|-----------------|
| Chrome Extension | Desktop Chrome users, paywall content | Chrome, Chromium-based |
| Bookmarklet | Universal fallback | All browsers including mobile Safari |

## Capture Modes

The Chrome extension supports two capture modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Full Page** (default) | Captures the rendered DOM from your browser | Paywall-gated content, JS-rendered SPAs, authenticated pages |
| **URL Only** | Sends only the URL for server-side fetching | Public articles, faster saves, smaller payloads |

Full page capture works because:
- The extension captures `document.documentElement.outerHTML` — exactly what you see in your browser
- Your authenticated session's content is captured, including paid articles and login-required pages
- Images are extracted and stored locally to ensure they persist

## Chrome Extension

### Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repository
5. Pin the extension by clicking the puzzle piece icon in your toolbar

### Configuration

1. Right-click the extension icon → **Options**
2. Enter your **API URL** (e.g., `https://your-app.railway.app` or `http://localhost:8000`)
3. Optionally enter an **API Key** if your instance requires authentication
4. Click **Save Settings**

### Usage

1. Navigate to any webpage
2. Optionally select text (captured as an excerpt)
3. Click the extension icon
4. Review pre-filled fields, add tags if desired
5. Toggle **"Capture full page"** based on your needs:
   - **On** (default): Captures the full rendered page — best for paywall content
   - **Off**: Sends only the URL for server-side extraction — faster for public pages
6. Click **Save**

The capture status indicator shows:
- ✓ "Full page captured" — DOM successfully captured
- "URL only" — URL-only mode selected
- "Capture failed (URL only)" — DOM capture failed, falling back to URL

### Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access current tab's URL and title when clicked |
| `scripting` | Capture selected text and full DOM from the active page |
| `storage` | Persist API URL, key, and capture mode settings across sessions |

## Bookmarklet

### Installation (Desktop)

1. Visit your instance's bookmarklet page: `https://YOUR_APP/api/v1/content/bookmarklet`
2. **Drag** the "Save to Aggregator" button to your bookmarks bar
3. Done! The bookmarklet is pre-configured with your server URL

### Installation (Mobile Safari)

1. Visit your instance's bookmarklet page
2. Create a regular bookmark for any page
3. Edit the bookmark and replace the URL with the bookmarklet code shown on the page
4. Rename the bookmark to "Save to Aggregator"

### Usage

1. Navigate to any webpage
2. Optionally select text
3. Click the bookmarklet in your bookmarks bar
4. A save form opens in a popup with URL, title, and selection pre-filled
5. Click **Save**

### How It Works

The bookmarklet executes a small JavaScript snippet that:
1. Captures `location.href` (current URL)
2. Captures `document.title` (page title)
3. Captures `window.getSelection()` (selected text, truncated to 500 chars)
4. Opens the save page with these as query parameters

## Save URL API

The bookmarklet and URL-only mode use this endpoint:

```
POST /api/v1/content/save-url
Content-Type: application/json

{
  "url": "https://example.com/article",
  "title": "Article Title",
  "excerpt": "Selected text excerpt",
  "tags": ["ai", "research"],
  "notes": "My notes about this article",
  "source": "chrome_extension"
}
```

**Response** (201):
```json
{
  "content_id": 123,
  "status": "queued",
  "message": "URL saved. Content extraction in progress.",
  "duplicate": false
}
```

## Save Page API (Full Page Capture)

The Chrome extension uses this endpoint when full page capture is enabled:

```
POST /api/v1/content/save-page
Content-Type: application/json

{
  "url": "https://example.com/article",
  "html": "<html>...(rendered DOM)...</html>",
  "title": "Article Title",
  "excerpt": "Selected text excerpt",
  "tags": ["ai", "research"],
  "source": "chrome_extension"
}
```

**Response** (201):
```json
{
  "content_id": 123,
  "status": "queued",
  "message": "Page saved. Content processing in progress.",
  "duplicate": false
}
```

### Key Differences from save-url

| Aspect | save-url | save-page |
|--------|----------|-----------|
| HTML source | Server fetches URL anonymously | Client sends rendered DOM |
| Paywall content | ❌ Blocked | ✓ Captured |
| JS-rendered SPAs | ❌ Empty shell | ✓ Full content |
| Image extraction | ❌ Not supported | ✓ Extracted & stored locally |
| Payload size | ~100 bytes | Up to 5 MB |
| Processing | Server-side fetch + parse | Parse client HTML directly |

### HTML Payload Limits

- Maximum HTML size: **5 MB**
- Maximum images per page: **20**
- Maximum image size: **5 MB** per image

Oversized payloads return HTTP 422 validation error.

### Status Polling

Check extraction progress:
```
GET /api/v1/content/{content_id}/status
```

**Response**:
```json
{
  "content_id": 123,
  "status": "parsed",
  "title": "Extracted Article Title",
  "word_count": 1542,
  "error": null
}
```

Status values: `pending` → `parsing` → `parsed` | `failed`

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `*` | CORS origins for cross-origin requests |

### Extension Settings (chrome.storage.sync)

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| `apiUrl` | Yes | - | Base URL of your Newsletter Aggregator instance |
| `apiKey` | No | - | API key or Supabase anon key for authentication |
| `captureFullPage` | No | `true` | Enable full page capture (DOM) vs URL-only mode |

## Troubleshooting

### Chrome Extension

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is correct and the server is running |
| "Save failed" (422) | The URL format may be invalid, or HTML payload too large |
| "Capture failed (URL only)" | DOM capture failed on this page; content restricted |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon and pin the extension |
| CORS error | Ensure `ALLOWED_ORIGINS` includes `chrome-extension://` or is set to `*` |
| Large page fails to save | Disable full page capture; HTML may exceed 5 MB limit |
| Images not extracted | Server downloads images after save; some may require auth |

### Bookmarklet

| Issue | Solution |
|-------|----------|
| Nothing happens on click | Ensure the bookmarklet URL starts with `javascript:` |
| Popup blocked | Allow popups for your Newsletter Aggregator domain |
| "Save failed" on popup | Check that your server is running and accessible |
| Bookmarklet doesn't capture selection | Selection must be made before clicking the bookmarklet |
| Mobile Safari issues | Ensure the bookmark URL is the full bookmarklet code, not a regular URL |

### API

| Issue | Solution |
|-------|----------|
| 422 Validation Error | Check URL format (must include `https://` or `http://`) |
| 404 Content Not Found | The content_id doesn't exist; check the save response |
| Extraction stuck on "pending" | Check server logs; the background extraction task may have failed |
| Duplicate detection returns wrong content | Duplicate check is by exact URL match including query params |
