# Newsletter Aggregator - Chrome Extension

Save any webpage to your Newsletter Aggregator instance with one click — including paywall-protected content.

## Features

- **Full page capture**: Captures the rendered DOM, including paywall and JS-rendered content
- **One-click save**: Click the extension icon to save the current page
- **Text selection**: Selected text is automatically captured as an excerpt
- **Capture mode toggle**: Switch between full page (default) and URL-only modes
- **Image extraction**: Images are downloaded and stored locally from captured pages
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
5. Choose your capture mode:
   - **Capture full page** (default, checkbox checked): Saves the rendered HTML including paywall content
   - **URL only** (checkbox unchecked): Sends only the URL for server-side extraction
6. Click **Save**

### Capture Status Indicator

The extension shows the capture status below the toggle:
- ✓ "Full page captured" — DOM captured successfully
- "URL only" — URL-only mode selected
- "Capture failed (URL only)" — DOM capture failed, falling back to URL mode

## Capture Modes

| Mode | Best For | What's Captured |
|------|----------|-----------------|
| **Full Page** | Paywall content, JS SPAs, login-required pages | Entire rendered DOM as you see it |
| **URL Only** | Public articles, faster saves | Just the URL; server fetches content |

**Why use full page capture?**
- Captures exactly what you see, including content behind paywalls
- Works with JavaScript-rendered single-page applications
- Extracts and stores images locally so they persist

## Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access the current tab's URL and title when you click the icon |
| `scripting` | Capture selected text and full DOM from the page |
| `storage` | Persist API URL, key, and capture mode preference across sessions |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is correct and the server is running |
| "Save failed" with 422 | URL format invalid, or HTML payload too large (>5 MB) |
| "Capture failed (URL only)" | DOM capture blocked on this page; use URL-only mode |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon in Chrome toolbar and pin the extension |
| Large page won't save | Try disabling "Capture full page"; page HTML may exceed 5 MB |
| Images missing in saved content | Server downloads images; some behind auth may fail |
