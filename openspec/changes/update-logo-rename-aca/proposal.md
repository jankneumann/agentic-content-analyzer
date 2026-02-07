# Change: Update Logo and Rename App to ACA (AI Content Analyzer)

## Why

The app has evolved beyond newsletter aggregation into a broader AI content analysis platform covering newsletters, RSS feeds, YouTube, podcasts, and file uploads. The current branding ("Newsletter Aggregator" with an "N" icon) no longer reflects the full scope of the product. A rebrand to "ACA — AI Content Analyzer" with a new logo (purple circuit-brain tree) better communicates the platform's capabilities and identity.

## What Changes

- Replace the current "N" letter logo (icon.svg and all PNG variants) with a new purple circuit-brain tree logo
- Rename all user-facing text from "Newsletter Aggregator" to "ACA" (short) / "AI Content Analyzer" (full)
- Update the sidebar brand section: abbreviation from "NA" → "ACA", full name from "Newsletter Aggregator" → "AI Content Analyzer"
- Update `index.html`: page title, meta description, apple-mobile-web-app-title
- Update `vite.config.ts`: PWA manifest name, short_name, and description
- Update favicon and PWA icon assets (all sizes: 192, 512, maskable, apple-touch-icon)

## Impact

- Affected specs: `frontend-tables` (sidebar branding), potentially `mobile-reader` (PWA manifest)
- Affected code:
  - `web/src/components/layout/Sidebar.tsx` — logo text and abbreviation
  - `web/index.html` — title, meta tags, favicon references
  - `web/vite.config.ts` — PWA manifest configuration
  - `web/public/icons/` — all icon assets (icon.svg, icon-192.png, icon-512.png, maskable variants, apple-touch-icon.png)
- No backend changes required
- No API changes
- No database changes
- **BREAKING**: PWA users may need to re-add the app to their home screen to see the new icon/name
