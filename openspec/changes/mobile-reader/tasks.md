# Implementation Tasks

## 1. PWA Plugin Setup

- [ ] 1.1 Install vite-plugin-pwa: `pnpm add -D vite-plugin-pwa`
- [ ] 1.2 Configure VitePWA in vite.config.ts with manifest options
- [ ] 1.3 Add workbox configuration for offline support
- [ ] 1.4 Configure registerType: 'autoUpdate' for automatic updates
- [ ] 1.5 Add navigateFallback for offline HTML page

## 2. App Icons

- [ ] 2.1 Create `web/public/icons/` directory
- [ ] 2.2 Generate icon-192.png (standard)
- [ ] 2.3 Generate icon-512.png (standard)
- [ ] 2.4 Generate icon-192-maskable.png (Android adaptive)
- [ ] 2.5 Generate icon-512-maskable.png (Android adaptive)
- [ ] 2.6 Generate apple-touch-icon.png (180x180)

## 3. iOS Support

- [ ] 3.1 Create iOS splash screen images for common device sizes
- [ ] 3.2 Add apple-touch-startup-image links to index.html
- [ ] 3.3 Add safe area CSS using env(safe-area-inset-*)
- [ ] 3.4 Test standalone detection with navigator.standalone
- [ ] 3.5 Add apple-mobile-web-app-capable meta tag

## 4. Offline Experience

- [ ] 4.1 Create `web/public/offline.html` with branded fallback
- [ ] 4.2 Configure navigateFallback in workbox options
- [ ] 4.3 Add navigateFallbackDenylist for /api/ routes
- [ ] 4.4 Style offline page with dark mode matching app theme

## 5. Update Notification Component

- [ ] 5.1 Create `web/src/components/PWAUpdatePrompt.tsx`
- [ ] 5.2 Use useRegisterSW hook from virtual:pwa-register/react
- [ ] 5.3 Add toast notification UI for new version available
- [ ] 5.4 Implement "Refresh" action to apply update
- [ ] 5.5 Add PWAUpdatePrompt to App.tsx

## 6. Playwright E2E Tests

- [ ] 6.1 Create `web/tests/e2e/pwa.spec.ts` test file
- [ ] 6.2 Add Mobile Chrome (Pixel 7) project to playwright.config.ts
- [ ] 6.3 Add Mobile Safari (iPhone 14) project to playwright.config.ts
- [ ] 6.4 Test service worker registration on page load
- [ ] 6.5 Test manifest is valid and linked correctly
- [ ] 6.6 Test offline mode using context.setOffline(true)
- [ ] 6.7 Test offline fallback page displays when network unavailable
- [ ] 6.8 Test mobile menu visibility on mobile viewport
- [ ] 6.9 Test app works after service worker update

## 7. Manual Device Testing

- [ ] 7.1 Test "Add to Home Screen" on iOS Safari
- [ ] 7.2 Test "Install App" on Android Chrome
- [ ] 7.3 Verify standalone mode (no browser chrome)
- [ ] 7.4 Test on notched device (iPhone with Dynamic Island)
- [ ] 7.5 Run Chrome DevTools Lighthouse PWA audit
- [ ] 7.6 Verify icons display correctly on home screen

## 8. Railway Deployment Verification

- [ ] 8.1 Deploy to Railway staging environment
- [ ] 8.2 Verify service worker serves over HTTPS
- [ ] 8.3 Verify manifest is accessible at /manifest.webmanifest
- [ ] 8.4 Test PWA installation from deployed URL
- [ ] 8.5 Test offline fallback on deployed app
- [ ] 8.6 Verify health check still passes with service worker

## 9. Documentation

- [ ] 9.1 Document installation flow for iOS users
- [ ] 9.2 Document installation flow for Android users
- [ ] 9.3 Add troubleshooting for common PWA issues
- [ ] 9.4 Document E2E test commands: `pnpm test:e2e`
- [ ] 9.5 Document known iOS PWA limitations

## COMPLETED (Reference Only)

These features are already implemented and require no changes:

- [x] Audio player - see audio-digest spec (`web/src/routes/audio-digests.tsx`)
- [x] Mobile save page - see mobile-cloud-infrastructure spec (`src/templates/save.html`)
- [x] React responsive layouts - existing Tailwind patterns in all components
- [x] Dark mode - existing Header.tsx toggle
- [x] Mobile sidebar overlay - AppShell.tsx
- [x] Playwright E2E setup - `web/playwright.config.ts`
- [x] Railway deployment - `railway.toml` configured with health checks
