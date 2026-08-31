# iOS Shortcuts for Newsletter Aggregator

This directory documents iOS Shortcuts for capturing web URLs from an iPhone.

> **Full documentation**: [Mobile Capture Guide](../docs/MOBILE_CAPTURE.md)
>
> **Interactive setup**: `https://your-server.com/api/v1/content/shortcut`
>
> Independently installed shortcuts that POST to `/api/v1/content/save-url`
> are unsupported. Recreate them from the installation page. See
> [API consumers](../docs/API_CONSUMERS.md).

## Installation

There is no checked-in `.shortcut` binary. Create the shortcut from the live
installation page or by hand:

1. Open the **Shortcuts** app
2. Tap **+**
3. Add:

```
1. Receive [URLs] from Share Sheet

2. Get Contents of URL
   - URL: [Your API URL]/api/v1/ingestions
   - Method: POST
   - Headers:
     - Content-Type: application/json
     - X-Admin-Key: [ADMIN_API_KEY]
   - Request Body (JSON):
     {
       "kind": "url",
       "url": "[Shortcut Input]"
     }

3. Show Result
   - Display operation_id
```

4. Name it **Save to Aggregator**
5. Enable **Show in Share Sheet**

Replace `[Your API URL]` with the API origin (Railway `aca-api`, not the
frontend origin), for example `https://aca-production-410f.up.railway.app`.

## Usage

1. Open Safari (or any app with a URL)
2. Tap **Share**
3. Tap **Save to Aggregator**
4. Confirm the returned `operation_id`

## API Reference

### POST /api/v1/ingestions

**Headers:** `Content-Type: application/json`, `X-Admin-Key: <key>`

**Request:**
```json
{
  "kind": "url",
  "url": "https://example.com/article",
  "title": "Optional title",
  "notes": "Optional selected text"
}
```

**Response (202):** `OperationHandle` with `schema_version: 2` and `operation_id`.

### GET /api/v1/operations/{operation_id}

Poll durable status.

Retired: `POST /api/v1/content/save-url` (404/405).
