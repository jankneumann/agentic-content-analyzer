## 1. Logo Asset Replacement

- [ ] 1.1 Save the new purple circuit-brain tree logo as the source image
- [ ] 1.2 Generate `icon.svg` from the new logo (or create an SVG version)
- [ ] 1.3 Generate `icon-192.png` (192x192) from the new logo
- [ ] 1.4 Generate `icon-512.png` (512x512) from the new logo
- [ ] 1.5 Generate `icon-192-maskable.png` (192x192, with safe zone padding)
- [ ] 1.6 Generate `icon-512-maskable.png` (512x512, with safe zone padding)
- [ ] 1.7 Generate `apple-touch-icon.png` and `apple-icon-180.png` (180x180)
- [ ] 1.8 Verify all icon files are correctly sized and display the new logo

## 2. App Name Update — Frontend Components

- [ ] 2.1 Update `Sidebar.tsx`: Change "NA" abbreviation to "ACA"
- [ ] 2.2 Update `Sidebar.tsx`: Change "Newsletter Aggregator" text to "AI Content Analyzer"

## 3. App Name Update — HTML & PWA Configuration

- [ ] 3.1 Update `index.html`: Change `<title>` from "Newsletter Aggregator" to "ACA — AI Content Analyzer"
- [ ] 3.2 Update `index.html`: Change meta description to reflect AI content analysis
- [ ] 3.3 Update `index.html`: Change `apple-mobile-web-app-title` from "Newsletters" to "ACA"
- [ ] 3.4 Update `vite.config.ts`: Change PWA manifest `name` to "ACA — AI Content Analyzer"
- [ ] 3.5 Update `vite.config.ts`: Change PWA manifest `short_name` to "ACA"
- [ ] 3.6 Update `vite.config.ts`: Change PWA manifest `description` to "AI-powered content analysis and digests"

## 4. Verification

- [ ] 4.1 Visual check: Sidebar displays new logo and "ACA" / "AI Content Analyzer"
- [ ] 4.2 Browser tab shows new favicon and updated title
- [ ] 4.3 PWA install prompt shows correct name and icon
- [ ] 4.4 Run E2E tests to check for any text-matching regressions (e.g., tests matching "Newsletter Aggregator")
