# Design: PWA Support with Offline Capability

## Context

The React frontend needs PWA support for mobile installation and offline fallback. Audio player, mobile navigation, and dark mode are already implemented.

## Goals

1. Enable "Add to Home Screen" on iOS and Android
2. Provide offline fallback when network unavailable
3. Support iOS-specific features (splash screens, safe areas)
4. Comprehensive E2E testing with Playwright

## Non-Goals

1. Native mobile apps (iOS/Android)
2. Full offline content sync (future enhancement)
3. Push notifications
4. Background audio controls (OS-level)
5. Audio player implementation (already done in audio-digest spec)

## Decisions

### Decision 1: Use vite-plugin-pwa

**What**: Use `vite-plugin-pwa` for PWA infrastructure.

**Why**: Industry standard for Vite-based apps. Provides:
- Automatic manifest generation from config
- Service worker via Workbox (production-tested)
- React hooks (`useRegisterSW`) for update UI
- Dev mode for testing during development

**Configuration**:
```typescript
// web/vite.config.ts
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'icons/*.png'],
      manifest: {
        name: 'Newsletter Aggregator',
        short_name: 'Newsletters',
        description: 'AI-powered newsletter aggregation and digests',
        theme_color: '#1a1a1a',
        background_color: '#1a1a1a',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-192-maskable.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/offline.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/api\./,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 300 } },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: { cacheName: 'image-cache', expiration: { maxEntries: 100, maxAgeSeconds: 86400 } },
          },
        ],
      },
    }),
  ],
})
```

### Decision 2: Workbox Caching Strategy

**What**: Use NetworkFirst for API, CacheFirst for static assets.

**Why**:
- **NetworkFirst** for API routes ensures fresh data when online
- **CacheFirst** for images/fonts provides faster loads
- **navigateFallback** shows offline page for uncached routes

| Resource Type | Strategy | Cache Duration |
|---------------|----------|----------------|
| API routes | NetworkFirst | 5 minutes |
| Static assets | CacheFirst | 24 hours |
| HTML pages | NetworkFirst | 5 minutes |
| Images | CacheFirst | 24 hours |

### Decision 3: Icon Generation

**What**: Generate icons using PWA Asset Generator or similar tool.

**Command**:
```bash
npx pwa-asset-generator logo.svg web/public/icons --background "#1a1a1a"
```

**Required Icons**:
| File | Size | Purpose |
|------|------|---------|
| `icon-192.png` | 192x192 | Standard icon |
| `icon-512.png` | 512x512 | Standard icon |
| `icon-192-maskable.png` | 192x192 | Android adaptive |
| `icon-512-maskable.png` | 512x512 | Android adaptive |
| `apple-touch-icon.png` | 180x180 | iOS home screen |

### Decision 4: iOS Splash Screens

**What**: Generate splash screens for common iOS device sizes.

**Device Coverage**:
| Device | Size | Scale |
|--------|------|-------|
| iPhone 14 Pro Max | 1290x2796 | 3x |
| iPhone 14 | 1170x2532 | 3x |
| iPhone SE | 750x1334 | 2x |
| iPad Pro 12.9" | 2048x2732 | 2x |
| iPad | 1640x2360 | 2x |

**HTML**:
```html
<link rel="apple-touch-startup-image"
      href="/icons/splash-1170x2532.png"
      media="(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)">
```

### Decision 5: Safe Area CSS

**What**: Use CSS `env()` for notched devices.

**Why**: iPhone Dynamic Island and Android cutouts need proper padding.

```css
/* Global safe area handling */
:root {
  --safe-area-top: env(safe-area-inset-top);
  --safe-area-bottom: env(safe-area-inset-bottom);
  --safe-area-left: env(safe-area-inset-left);
  --safe-area-right: env(safe-area-inset-right);
}

/* Apply to fixed headers */
.app-header {
  padding-top: calc(1rem + var(--safe-area-top));
}

/* Apply to bottom navigation */
.bottom-nav {
  padding-bottom: calc(1rem + var(--safe-area-bottom));
}
```

### Decision 6: Service Worker Update UX

**What**: Show toast notification when new version available.

**Why**: Users should know updates are available without forced refresh.

```tsx
// web/src/components/PWAUpdatePrompt.tsx
import { useRegisterSW } from 'virtual:pwa-register/react'

export function PWAUpdatePrompt() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  if (!needRefresh) return null

  return (
    <div className="fixed bottom-4 left-4 right-4 bg-blue-600 text-white p-4 rounded-lg shadow-lg flex justify-between items-center">
      <span>New version available!</span>
      <button
        onClick={() => updateServiceWorker(true)}
        className="bg-white text-blue-600 px-4 py-2 rounded font-medium"
      >
        Refresh
      </button>
    </div>
  )
}
```

### Decision 7: Offline Fallback Page

**What**: Branded static HTML page shown when offline.

**Why**: Better UX than browser's default offline error.

```html
<!-- web/public/offline.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Offline - Newsletter Aggregator</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      background: #1a1a1a;
      color: #e0e0e0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 1rem;
      text-align: center;
    }
    h1 { margin-bottom: 0.5rem; }
    p { color: #888; margin-bottom: 2rem; }
    button {
      background: #6366f1;
      color: white;
      border: none;
      padding: 1rem 2rem;
      border-radius: 0.5rem;
      font-size: 1rem;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <h1>You're offline</h1>
  <p>Check your connection and try again</p>
  <button onclick="window.location.reload()">Retry</button>
</body>
</html>
```

### Decision 8: Playwright E2E Testing Strategy

**What**: Comprehensive PWA E2E tests using Playwright.

**Why**: PWA features are critical for mobile UX and must be tested automatically.

**Mobile Device Projects**:
```typescript
// web/playwright.config.ts
projects: [
  { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  { name: 'Mobile Chrome', use: { ...devices['Pixel 7'] } },
  { name: 'Mobile Safari', use: { ...devices['iPhone 14'] } },
],
```

**Test Scenarios**:

1. **Service Worker Registration**
```typescript
test('service worker registers on page load', async ({ page }) => {
  await page.goto('/')
  const swRegistration = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration()
    return reg !== undefined
  })
  expect(swRegistration).toBe(true)
})
```

2. **Offline Fallback**
```typescript
test('offline fallback page displays when offline', async ({ page, context }) => {
  await page.goto('/')
  await page.waitForFunction(() => navigator.serviceWorker.ready)
  await context.setOffline(true)
  await page.goto('/some-uncached-page')
  await expect(page.locator('text=You are offline')).toBeVisible()
})
```

3. **Manifest Validity**
```typescript
test('manifest is valid and accessible', async ({ page }) => {
  const response = await page.goto('/manifest.webmanifest')
  expect(response?.status()).toBe(200)
  const manifest = await response?.json()
  expect(manifest.name).toBe('Newsletter Aggregator')
  expect(manifest.icons.length).toBeGreaterThanOrEqual(2)
  expect(manifest.display).toBe('standalone')
})
```

4. **Mobile Viewport Tests**
```typescript
test('app is usable on mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }) // iPhone 14
  await page.goto('/')
  await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible()
})
```

## File Structure

```
web/
├── public/
│   ├── icons/
│   │   ├── icon-192.png
│   │   ├── icon-512.png
│   │   ├── icon-192-maskable.png
│   │   ├── icon-512-maskable.png
│   │   ├── apple-touch-icon.png
│   │   └── splash-*.png (iOS splash screens)
│   └── offline.html
├── src/
│   └── components/
│       └── PWAUpdatePrompt.tsx
├── tests/
│   └── e2e/
│       └── pwa.spec.ts
├── vite.config.ts (modified)
├── playwright.config.ts (modified)
└── package.json (modified)
```

## Chrome PWA Installability Criteria (2025-2026)

| Criterion | How We Meet It |
|-----------|----------------|
| HTTPS | Railway deployment with HTTPS |
| Valid manifest | Generated by vite-plugin-pwa |
| Service worker with fetch handler | Generated by vite-plugin-pwa with Workbox |
| User engagement (30s + click) | Document in user docs |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Service worker caching stale content | Use `registerType: 'autoUpdate'` with user notification |
| iOS PWA limitations | Document known limitations (no push, no badges) |
| Offline fallback not working | E2E tests verify offline behavior |
| Icon generation complexity | Use pwa-asset-generator for automation |
| Safe areas not applied correctly | E2E tests with mobile viewports |
