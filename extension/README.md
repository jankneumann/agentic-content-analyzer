# Newsletter Aggregator - Chrome Extension

Save any webpage to your Newsletter Aggregator instance with one click.

## Features

- **One-click save**: Click the extension icon to save the current page
- **Text selection**: Selected text is automatically captured as an excerpt
- **Tags**: Add comma-separated tags to organize saved content
- **Dark mode**: Adapts to your system color scheme
- **Status feedback**: Immediate success/error feedback after saving

## Installation (Load Unpacked)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repository
5. The extension icon will appear in your toolbar

## Configuration

1. Right-click the extension icon and select **Options** (or click the gear icon in Chrome's extension management)
2. Enter your **API URL** (e.g., `https://your-app.example.com`)
3. Optionally enter an **API Key** if your instance requires authentication
4. Click **Save Settings**

## Usage

1. Navigate to any webpage you want to save
2. Optionally select text on the page (it will be captured as an excerpt)
3. Click the extension icon in your toolbar
4. Review the pre-filled URL, title, excerpt, and add tags if desired
5. Click **Save**

## Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access the current tab's URL and title when you click the icon |
| `scripting` | Capture selected text from the page |
| `storage` | Persist your API URL and key settings across sessions |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is correct and the server is running |
| "Save failed" with 422 | The URL format may be invalid |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon in Chrome toolbar and pin the extension |
