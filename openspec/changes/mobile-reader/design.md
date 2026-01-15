# Design: Mobile Reader & Audio Playback

## Context

Users want to consume content on mobile devices. The current web UI needs mobile optimization and audio playback support.

## Goals

1. Responsive layouts for all content types
2. Touch-friendly audio player
3. PWA support for home screen installation
4. Clean reading experience on small screens

## Non-Goals

1. Native mobile apps (iOS/Android)
2. Offline sync (can add later with service worker)
3. Push notifications
4. Background audio controls (OS-level)

## Decisions

### Decision 1: Mobile-First CSS

**What**: Use responsive CSS with mobile-first breakpoints.

```css
/* Base styles for mobile */
.content-body {
  font-size: 18px;
  line-height: 1.6;
  padding: 1rem;
}

/* Tablet and up */
@media (min-width: 768px) {
  .content-body {
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem;
  }
}
```

### Decision 2: HTML5 Audio Player

**What**: Custom-styled HTML5 audio element with controls.

**Why**: Native controls vary by browser. Custom UI provides consistent experience.

```html
<div class="audio-player" data-audio-url="{{ audio_url }}">
  <audio id="audio" preload="metadata">
    <source src="{{ audio_url }}" type="audio/mpeg">
  </audio>
  <div class="player-controls">
    <button class="play-pause">▶</button>
    <input type="range" class="seek-bar" value="0">
    <span class="time-display">0:00 / 0:00</span>
    <select class="playback-speed">
      <option value="1">1x</option>
      <option value="1.5">1.5x</option>
      <option value="2">2x</option>
    </select>
  </div>
</div>
```

### Decision 3: PWA Manifest

**What**: Web app manifest for installability.

```json
{
  "name": "Newsletter Aggregator",
  "short_name": "Newsletters",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1a1a1a",
  "icons": [
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### Decision 4: Dark Mode

**What**: Support system dark mode preference.

```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg-color: #1a1a1a;
    --text-color: #e0e0e0;
    --accent-color: #6366f1;
  }
}
```

### Decision 5: Typography for Reading

**What**: Optimize typography for long-form reading.

```css
.content-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  font-size: clamp(16px, 4vw, 20px);
  line-height: 1.7;
  letter-spacing: 0.01em;
}

.content-body h1, h2, h3 {
  line-height: 1.3;
  margin-top: 2em;
}
```

## File Structure

```
src/static/
├── manifest.json
├── icons/
│   ├── icon-192.png
│   ├── icon-512.png
│   └── apple-touch-icon.png
├── css/
│   ├── mobile.css
│   └── audio-player.css
└── js/
    └── audio-player.js

src/templates/
├── base.html              # Add manifest, viewport meta
├── components/
│   └── audio-player.html  # Reusable player component
└── shared/
    ├── content.html       # Mobile-optimized
    ├── summary.html       # Mobile-optimized
    └── digest.html        # Mobile-optimized with player
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Audio not playing on iOS | Add user interaction requirement note |
| Large audio files on mobile data | Show file size, offer download option |
| PWA not working in all browsers | Graceful degradation to regular web |
