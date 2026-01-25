# iOS Shortcuts for Newsletter Aggregator

This directory contains iOS Shortcut files for capturing web content from your iPhone.

## Installation

### Option 1: Import from File

1. Transfer the `.shortcut` file to your iPhone (AirDrop, iCloud, email)
2. Open the file - it will open in the Shortcuts app
3. Tap "Add Shortcut"
4. Configure your API URL (see Configuration below)

### Option 2: Create Manually

If you prefer to create the Shortcut yourself:

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new Shortcut
3. Add the following actions:

#### Shortcut Actions

```
1. Receive [URLs] from Share Sheet
   - Types: URLs

2. Set Variable
   - Name: url
   - Value: Shortcut Input

3. Text
   {
     "url": "[url]",
     "source": "ios_shortcut"
   }

4. Get Contents of URL
   - URL: [Your API URL]/api/v1/content/save-url
   - Method: POST
   - Headers:
     - Content-Type: application/json
   - Request Body: [Text from step 3]

5. If [Status Code] is 201 or 200
   - Show Notification: "Saved!"
6. Otherwise
   - Show Alert: "Save failed: [Response]"
```

## Configuration

After installing the Shortcut:

1. Open the Shortcuts app
2. Find "Save to Newsletter"
3. Tap the **...** (three dots) to edit
4. Find the "Get Contents of URL" action
5. Replace `[Your API URL]` with your actual server URL

### Example URLs

- **Local development**: `http://192.168.1.x:8000` (your computer's IP)
- **Railway**: `https://your-app.railway.app`
- **Fly.io**: `https://your-app.fly.dev`

## Usage

1. Open Safari (or any app with a URL)
2. Tap the **Share** button
3. Scroll down and tap **"Save to Newsletter"**
4. Wait for the success notification

## Troubleshooting

### "Could not connect to server"

- Check that your API server is running
- Verify the URL is correct
- For local development, ensure your phone is on the same WiFi network

### "Save failed"

- Check the server logs for errors
- Verify the database is accessible
- Ensure CORS is configured (set `ALLOWED_ORIGINS=*` in your .env)

### Shortcut doesn't appear in Share Sheet

- Open Settings > Shortcuts
- Enable "Allow Sharing Large Amounts of Data"
- Restart the Shortcuts app

## API Reference

### POST /api/v1/content/save-url

Saves a URL for content extraction.

**Request:**
```json
{
  "url": "https://example.com/article",
  "title": "Optional title",
  "excerpt": "Optional selected text",
  "source": "ios_shortcut"
}
```

**Response (201 Created):**
```json
{
  "content_id": 123,
  "status": "queued",
  "message": "URL saved. Content extraction in progress.",
  "duplicate": false
}
```

### GET /api/v1/content/{id}/status

Check extraction status.

**Response:**
```json
{
  "content_id": 123,
  "status": "parsed",
  "title": "Article Title",
  "word_count": 1500
}
```
