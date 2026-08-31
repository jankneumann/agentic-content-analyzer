# Mobile Content Capture

Save articles, blog posts, and other web content directly from your mobile device.

Canonical URL capture uses the durable ingestion workflow. Independently
installed iOS Shortcuts that still call `POST /api/v1/content/save-url` must be
recreated; that mutation is retired. See [API consumers](API_CONSUMERS.md).

## Overview

| Method | Platform | Setup | Best For |
|--------|----------|-------|----------|
| iOS Shortcut | iPhone/iPad | One-time setup | Daily use, Share Sheet integration |
| Bookmarklet | Any browser | One-time setup | Desktop and mobile browsers |
| Web Save Page | Any device | No setup | Quick saves, fallback method |
| Chrome Extension | Desktop Chrome | Install extension | URL capture from the toolbar |

## iOS Shortcut Setup

### Prerequisites
- iPhone or iPad running iOS 15+
- Your Aggregator server URL (e.g. `https://app.aca.rotkohl.ai`)
- Production requires `X-Admin-Key` with `ADMIN_API_KEY`

### Creating the Shortcut

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new shortcut
3. Add these actions in order:

**Action 1: Receive input**
- Choose "Receive **URLs** from **Share Sheet**"

**Action 2: Get Contents of URL**
- URL: `https://your-server.com/api/v1/ingestions`
- Method: POST
- Headers:
  - `Content-Type`: `application/json`
  - `X-Admin-Key`: `your-api-key`
- Request Body (JSON):
  ```json
  {
    "kind": "url",
    "url": "[Shortcut Input]"
  }
  ```

**Action 3: Show Result**
- Display `operation_id` from the JSON response

4. Name the shortcut "Save to Aggregator"
5. Tap the shortcut settings (i) and enable **Show in Share Sheet**

### Using the Shortcut

1. Open any article in Safari (or any app with a Share button)
2. Tap the **Share** button
3. Scroll down and tap **Save to Aggregator**
4. The shortcut queues durable ingestion and shows the operation id

### Installation Page

Visit `https://your-server.com/api/v1/content/shortcut` for a guided setup page
with your server URL pre-configured. That page is the source of truth for the
shortcut contract.

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
- Submits `POST /api/v1/ingestions` with `kind: url` and shows `operation_id`

## Chrome Extension

See [Content Capture](CONTENT_CAPTURE.md#chrome-extension). URL-only capture
posts the same `IngestCommand`. Client-supplied HTML (`save-page`) is retired;
the extension falls back to URL ingestion.

## API Reference

### Queue URL ingestion

```
POST /api/v1/ingestions
Content-Type: application/json
X-Admin-Key: <ADMIN_API_KEY>
```

```json
{
  "kind": "url",
  "url": "https://example.com/article",
  "title": "Optional title",
  "tags": ["ai", "research"],
  "notes": "Optional notes"
}
```

`source` and `excerpt` are not fields on `UrlIngestCommand`. Unknown fields are
rejected (`additionalProperties: false`). Selected text belongs in `notes`.

**Response** (202):
```json
{
  "schema_version": 2,
  "operation_id": "104",
  "operation_type": "ingestion.execute",
  "status": "queued",
  "progress": 0,
  "message": "...",
  "cancellable": true,
  "retry_count": 0,
  "status_url": "/api/v1/operations/104",
  "events_url": "/api/v1/operations/104/events"
}
```

### Check status

```
GET /api/v1/operations/{operation_id}
X-Admin-Key: <ADMIN_API_KEY>
```

### Retired mutations

These return 404/405 and must not be used:

- `POST /api/v1/content/save-url`
- `POST /api/v1/content/save-page`

There is **no compatibility window** for independently installed shortcuts or
bookmarklets that still call the retired routes. Recreate them from
`/api/v1/content/shortcut` or `/api/v1/content/bookmarklet`.

## Authentication

Production requires `X-Admin-Key` (the raw `ADMIN_API_KEY`). Session cookies
work for the web UI. `Authorization: Bearer` is not the capture-client header.

## Troubleshooting

### iOS Shortcut Issues

| Problem | Solution |
|---------|----------|
| "Could not connect to server" | Check server URL is correct and reachable |
| "401 Unauthorized" / "403 Forbidden" | Add `X-Admin-Key` with `ADMIN_API_KEY` |
| 422 Unprocessable Entity | Body must include `"kind": "url"`; do not send `source` |
| Shortcut not in Share Sheet | Shortcuts app → shortcut → Settings (i) → enable Share Sheet |
| 404 on `/api/v1/content/save-url` | The shortcut is the pre-cutover variant. Recreate it |

### Bookmarklet Issues

| Problem | Solution |
|---------|----------|
| "Pop-up blocked" | Allow pop-ups for your server domain |
| Save form shows wrong server URL | Reinstall from `/api/v1/content/bookmarklet` |

### Web Save Page Issues

| Problem | Solution |
|---------|----------|
| "Error: Failed to fetch" | Check `/health`; confirm CORS `ALLOWED_ORIGINS` |
