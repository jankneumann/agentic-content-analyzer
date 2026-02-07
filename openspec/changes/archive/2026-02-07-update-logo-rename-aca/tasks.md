## 1. Logo Asset Replacement

- [x] 1.1 Source logo uploaded as `web/public/icons/rotkohl-logo-source.png`
- [x] 1.2 Generate `icon.svg` from `rotkohl-logo-source.png` (or create an SVG version)
- [x] 1.3 Generate `icon-192.png` (192x192) from the new logo
- [x] 1.4 Generate `icon-512.png` (512x512) from the new logo
- [x] 1.5 Generate `icon-192-maskable.png` (192x192, with safe zone padding)
- [x] 1.6 Generate `icon-512-maskable.png` (512x512, with safe zone padding)
- [x] 1.7 Generate `apple-touch-icon.png` and `apple-icon-180.png` (180x180)
- [x] 1.8 Verify all icon files are correctly sized and display the new logo

## 2. App Name Update — Frontend Components

- [x] 2.1 Update `Sidebar.tsx`: Replace "NA" text with logo image, show "ACA" alt text
- [x] 2.2 Update `Sidebar.tsx`: Change "Newsletter Aggregator" text to "AI Content Analyzer"

## 3. App Name Update — HTML & PWA Configuration

- [x] 3.1 Update `index.html`: Change `<title>` from "Newsletter Aggregator" to "ACA — AI Content Analyzer"
- [x] 3.2 Update `index.html`: Change meta description to reflect AI content analysis
- [x] 3.3 Update `index.html`: Change `apple-mobile-web-app-title` from "Newsletters" to "ACA"
- [x] 3.4 Update `vite.config.ts`: Change PWA manifest `name` to "ACA — AI Content Analyzer"
- [x] 3.5 Update `vite.config.ts`: Change PWA manifest `short_name` to "ACA"
- [x] 3.6 Update `vite.config.ts`: Change PWA manifest `description` to "AI-powered content analysis and digests"

## 4. Verification

- [x] 4.1 Visual check: Sidebar displays new logo and "ACA" / "AI Content Analyzer"
- [x] 4.2 Browser tab shows new favicon and updated title (manual verification — deferred to deploy)
- [x] 4.3 PWA install prompt shows correct name and icon (manual verification — deferred to deploy)
- [x] 4.4 Run E2E tests to check for any text-matching regressions (e.g., tests matching "Newsletter Aggregator")
