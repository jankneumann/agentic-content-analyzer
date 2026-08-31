# Newsletter Aggregator - Chrome Extension

Queue the current page URL into durable ingestion with one click.

Full-page HTML capture (`POST /api/v1/content/save-page`) is **retired**.
The extension always posts `POST /api/v1/ingestions` with `kind: url`.
Reload the unpacked extension from this directory after pulling `main`.

## Features

- **One-click save**: Click the extension icon to queue the current page URL
- **Text selection**: Selected text is sent as `notes`
- **Tags**: Add comma-separated tags
- **Dark mode**: Adapts to your system color scheme
- **Status feedback**: Shows the returned `operation_id`

## Installation (Load Unpacked)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repository
5. The extension icon will appear in your toolbar

## Configuration

1. Right-click the extension icon and select **Options**
2. Enter your **API URL** (the `aca-api` origin, not the frontend origin)
3. Enter **API Key** (`ADMIN_API_KEY`, sent as `X-Admin-Key`)
4. Click **Save Settings**

## Usage

1. Navigate to any webpage you want to save
2. Optionally select text on the page (captured as `notes`)
3. Click the extension icon in your toolbar
4. Review the pre-filled URL, title, excerpt, and add tags if desired
5. Click **Save**

The request body is:

```json
{
  "kind": "url",
  "url": "https://example.com/article",
  "title": "Page title",
  "tags": ["ai"],
  "notes": "selected text"
}
```

Success is HTTP 202 with an `OperationHandle` (`schema_version: 2`,
`operation_id`). Poll `GET /api/v1/operations/{operation_id}`.

Paywall and JS-rendered pages that the server cannot fetch anonymously will
not round-trip through the extension. Restoring client-supplied HTML requires
a URL-major (`/api/v2`) or a new ingest `kind`. See
[API consumers](../docs/API_CONSUMERS.md).

## Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access the current tab's URL and title when you click the icon |
| `scripting` | Capture selected text from the page |
| `storage` | Persist API URL and key across sessions |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is the API origin and the server is running |
| "Save failed" with 422 | Body must include `"kind": "url"`; do not send `source`, `excerpt`, or HTML |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon in Chrome toolbar and pin the extension |
| Empty content behind a paywall | Client-supplied HTML is retired; the server fetches the URL |
