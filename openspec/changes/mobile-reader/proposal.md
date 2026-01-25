# Change: Add PWA Support with Offline Capability

## Why

Enable app-like mobile experience with installation and offline support:

1. **Add to Home Screen**: Install on iOS/Android for quick access
2. **Standalone Mode**: Full-screen without browser chrome
3. **Offline Fallback**: Basic functionality when network unavailable
4. **Consistent Branding**: App icons, splash screens, theme colors

## What's Already Done (No Changes)

The following features are already implemented and require no changes:

| Feature | Source | Status |
|---------|--------|--------|
| Audio player | `audio-digest` spec | ✅ Full player with seek, speed, volume |
| Mobile save page | `mobile-cloud-infrastructure` spec | ✅ Dark mode, responsive |
| React mobile navigation | `AppShell.tsx` | ✅ Sidebar overlay |
| Dark mode support | `Header.tsx` | ✅ Theme toggle |
| E2E testing infrastructure | `web/playwright.config.ts` | ✅ Playwright ready |
| Railway deployment | `railway.toml` | ✅ Health checks configured |

## What's Included

### PWA Infrastructure (vite-plugin-pwa)
- Automatic manifest generation from vite.config.ts
- Service worker with Workbox for offline support
- Auto-update strategy with user notification
- React hooks for update UI

### App Icons
- Standard icons: 192x192, 512x512 PNG
- Maskable icons for Android adaptive icon support
- Apple touch icon: 180x180 PNG
- iOS splash screens for common device sizes

### Offline Experience
- Offline fallback page when network unavailable
- Cached shell for immediate app loading
- "You're offline" indicator with retry button

### iOS-Specific Support
- Apple touch startup images (splash screens)
- Safe area CSS for notched devices
- Standalone mode detection

### E2E Testing (Playwright)
- Service worker registration verification
- Offline mode functionality
- Manifest validity checks
- Mobile viewport tests

## Dependencies

- **None** - Decoupled from content-sharing proposal
- Mobile responsiveness is handled by existing Tailwind classes

## Impact

- **MODIFIED**: `web/vite.config.ts` - Add vite-plugin-pwa configuration
- **MODIFIED**: `web/package.json` - Add vite-plugin-pwa dependency
- **MODIFIED**: `web/playwright.config.ts` - Add mobile device projects
- **NEW**: `web/public/icons/` - App icons directory
- **NEW**: `web/public/offline.html` - Offline fallback page
- **NEW**: `web/src/components/PWAUpdatePrompt.tsx` - Update notification
- **NEW**: `web/tests/e2e/pwa.spec.ts` - PWA E2E tests

## Configuration

```bash
# Optional: Custom app name for PWA (in vite.config.ts)
# These are configured in the VitePWA plugin options
```

## Related Proposals

This proposal is **decoupled** from the original Supabase integration series:

- ✅ `supabase-database` - Complete
- ✅ `supabase-storage` - Complete
- ✅ `audio-digest` - Complete (audio player already done)
- ✅ `mobile-cloud-infrastructure` - Complete (save page already done)
- 🔄 `mobile-reader` (this proposal) - PWA support only
