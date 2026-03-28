# Mobile Content Capture

Save articles, blog posts, and other web content directly from your mobile device.

## Overview

The Newsletter Aggregator supports multiple mobile capture methods:

| Method | Platform | Setup | Best For |
|--------|----------|-------|----------|
| iOS Shortcut | iPhone/iPad | One-time setup | Daily use, Share Sheet integration |
| Bookmarklet | Any browser | One-time setup | Desktop and mobile browsers |
| Web Save Page | Any device | No setup | Quick saves, fallback method |
| Chrome Extension | Desktop Chrome | Install extension | Full page capture with JS rendering |

## iOS Shortcut Setup

### Prerequisites
- iPhone or iPad running iOS 15+
- Your Newsletter Aggregator server URL (e.g., `https://your-app.railway.app`)
- Optional: API key for authenticated access

### Creating the Shortcut

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new shortcut
3. Add these actions in order:

**Action 1: Receive input**
- Choose "Receive **URLs** from **Share Sheet**"

**Action 2: Get Contents of URL**
- URL: `https://your-server.com/api/v1/content/save-url`
- Method: POST
- Headers:
  - `Content-Type`: `application/json`
  - `X-Admin-Key`: `your-api-key` (optional, for authenticated servers)
- Request Body (JSON):
  ```json
  {
    "url": "[Shortcut Input]",
    "source": "ios_shortcut"
  }
  ```

**Action 3: Show Result**
- Shows the API response for confirmation

4. Name the shortcut "Save to Newsletter"
5. Tap the shortcut settings (i) and enable **Show in Share Sheet**

### Using the Shortcut

1. Open any article in Safari (or any app with a Share button)
2. Tap the **Share** button
3. Scroll down and tap **Save to Newsletter**
4. The shortcut sends the URL and shows a confirmation

### Installation Page

Visit `https://your-server.com/api/v1/content/shortcut` for a guided setup page with your server URL pre-configured.

## Bookmarklet Setup

Visit `https://your-server.com/api/v1/content/bookmarklet` to install.

### Desktop
1. Open the bookmarklet page
2. Drag the "Save to Aggregator" button to your bookmarks bar
3. On any page, click the bookmarklet to open the save form

### Mobile (iOS Safari)
1. Visit the bookmarklet page
2. Add a regular bookmark for any page
3. Edit the bookmark and replace the URL with the bookmarklet code shown on the page

## Web Save Page

Visit `https://your-server.com/api/v1/content/save` to save URLs manually.

- Enter a URL and optional title/notes
- Works on any device with a browser
- No installation required
- Recent saves are stored locally for quick reference

## Chrome Extension

See [Content Capture](CONTENT_CAPTURE.md#chrome-extension) for Chrome extension setup.

## API Reference

### Save URL
```
POST /api/v1/content/save-url
Content-Type: application/json

{
  "url": "https://example.com/article",
  "title": "Optional title",
  "tags": ["ai", "research"],
  "notes": "Optional notes",
  "source": "ios_shortcut"
}
```

**Response** (201):
```json
{
  "content_id": 12345,
  "status": "queued",
  "message": "URL saved. Content extraction in progress.",
  "duplicate": false
}
```

### Check Status
```
GET /api/v1/content/{content_id}/status
```

### Rate Limiting
- **Limit**: 30 requests per minute per IP address
- **429 Response**: Includes `Retry-After` header with seconds until reset
- Rate limits are shared across both endpoints — 30 requests total per minute across save-url and save-page combined

## Authentication

### Development Mode
- No authentication required when `APP_SECRET_KEY` and `ADMIN_API_KEY` are not configured

### Production Mode
Two authentication methods are supported:
1. **Session Cookie**: Log in via the web UI, cookie is sent automatically
2. **API Key**: Set `X-Admin-Key` header (for Shortcuts and programmatic access)

## Troubleshooting

### iOS Shortcut Issues

| Problem | Solution |
|---------|----------|
| "Could not connect to server" | Check server URL is correct and accessible from your network |
| "401 Unauthorized" | Add `X-Admin-Key` header with your API key |
| "429 Too Many Requests" | Wait 60 seconds, you've hit the rate limit |
| Shortcut not in Share Sheet | Open Shortcuts app, tap shortcut, Settings (i), enable "Show in Share Sheet" |
| "URL already saved" | This is normal -- the URL was previously captured. Status will show "exists" |

### Bookmarklet Issues

| Problem | Solution |
|---------|----------|
| "Pop-up blocked" | Allow pop-ups for your server domain in browser settings |
| Save form shows wrong server URL | Reinstall bookmarklet from your server's `/bookmarklet` page |
| Form submits but nothing happens | Check browser console for CORS errors; verify `ALLOWED_ORIGINS` includes your frontend URL |

### Web Save Page Issues

| Problem | Solution |
|---------|----------|
| Recent saves not showing | Check localStorage is not disabled; try clearing and re-saving |
| "Error: Failed to fetch" | Server may be down; check `/health` endpoint |
