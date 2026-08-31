# Content Capture Guide

Save web content to your Newsletter Aggregator while browsing. Two capture methods are available:

| Method | Best For | Browser Support |
|--------|----------|-----------------|
| Chrome Extension | Desktop Chrome users | Chrome, Chromium-based |
| Bookmarklet | Universal fallback | All browsers including mobile Safari |

## Mobile Capture

For mobile-specific setup (iOS Shortcuts, mobile bookmarklets, web save page):
see the **[Mobile Capture Guide](MOBILE_CAPTURE.md)**.

## Capture Modes

URL capture is the supported mutation. The extension always submits
`POST /api/v1/ingestions` with `kind: url`. Server-side extraction follows
`classify_url` (YouTube, RSS, or webpage).

Client-supplied HTML (`POST /api/v1/content/save-page`) is **retired**. Paywall
and JS-rendered pages that cannot be fetched anonymously will not round-trip
through the extension until a future URL-major command exists. See
[API consumers](API_CONSUMERS.md).

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
3. Enter an **API Key** (`ADMIN_API_KEY`, sent as `X-Admin-Key`)
4. Click **Save Settings**

### Usage

1. Navigate to any webpage
2. Optionally select text (captured as an excerpt)
3. Click the extension icon
4. Review pre-filled fields, add tags if desired
5. Click **Save**. The extension queues `kind: url` ingestion and shows `operation_id`.

### Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access current tab's URL and title when clicked |
| `scripting` | Capture selected text from the active page |
| `storage` | Persist API URL and key across sessions |

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

## URL ingestion API

The bookmarklet, web save page, shortcut, and extension URL capture use:

```
POST /api/v1/ingestions
Content-Type: application/json
X-Admin-Key: <ADMIN_API_KEY>
```

```json
{
  "kind": "url",
  "url": "https://example.com/article",
  "title": "Article Title",
  "tags": ["ai", "research"],
  "notes": "Selected text excerpt"
}
```

**Response** (202): `OperationHandle` (`schema_version: 2`, `operation_id`,
`status_url`). Poll `GET /api/v1/operations/{operation_id}`.

`POST /api/v1/content/save-url` is retired (404/405).

### Auto-routing

Saved URLs are **auto-routed** to the appropriate ingest handler based on the
URL shape (`src/ingestion/url_router.py`, `classify_url`):

| URL shape | Route | Handler |
|-----------|-------|---------|
| `youtube.com/watch?v=…`, `youtu.be/…` | `youtube_video` | YouTube transcript/analysis; fills this row in place |
| `youtube.com/playlist?list=…` | `youtube_playlist` | Playlist ingestion (entries become their own rows; this row becomes a receipt) |
| `…/feed`, `*.rss`, `*.atom`, `?feed=…`, `*.substack.com/feed` | `rss_feed` | RSS ingestion (entries become their own rows; this row becomes a receipt) |
| anything else | `webpage` | Generic Trafilatura extraction (unchanged) |

Classification is deterministic and network-free (URL patterns only). The
chosen route is recorded on the row's `metadata_json.route` after the durable
operation completes. The HTTP response is the `202` handle, not a completed
content row.

The same routing powers the CLI: `aca ingest url <url>` routes by default; pass
`--no-route` to force generic web-page extraction regardless of the URL.

## Save Page API (retired)

`POST /api/v1/content/save-page` is not composed. Full-page HTML capture is not
on `UrlIngestCommand`. Restoring it requires a URL-major (`/api/v2`) or a new
ingest `kind`, not an in-place `/api/v1` adapter.

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `*` | CORS origins for cross-origin requests |

### Extension Settings (chrome.storage.sync)

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| `apiUrl` | Yes | - | API origin (the `aca-api` host, not the frontend origin) |
| `apiKey` | Production | - | Sent as `X-Admin-Key` (`ADMIN_API_KEY`) |

## Troubleshooting

### Chrome Extension

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is correct and the server is running |
| "Save failed" (422) | Body must be `{ "kind": "url", "url": "https://..." }`; unknown fields are rejected |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon and pin the extension |
| CORS error | Ensure `ALLOWED_ORIGINS` includes `chrome-extension://` or is set to `*` |
| Paywall / JS-only page is empty | Client-supplied HTML is retired; server fetches the URL anonymously |
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
| 404 Content Not Found | Poll `GET /api/v1/operations/{operation_id}`, not the retired save-url body |
| Extraction stuck on "queued" | Check `GET /api/v1/operations/{id}`; workers may not be running |
| Duplicate detection returns wrong content | Duplicate check is by exact URL match including query params |
