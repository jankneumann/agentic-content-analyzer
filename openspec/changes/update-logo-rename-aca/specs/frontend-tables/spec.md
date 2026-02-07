## MODIFIED Requirements

### Requirement: Sidebar Branding

The sidebar component SHALL display the app identity using the ACA brand:

- In collapsed mode, the sidebar SHALL display the text "ACA" in the primary color as the logo badge.
- In expanded mode, the sidebar SHALL display the "ACA" badge followed by the full name "AI Content Analyzer".
- The sidebar logo area SHALL use a 16px-height header with a bottom border.

#### Scenario: Sidebar collapsed shows ACA abbreviation
- **WHEN** the sidebar is in collapsed mode
- **THEN** the sidebar displays "ACA" as the logo badge in the primary color

#### Scenario: Sidebar expanded shows full brand name
- **WHEN** the sidebar is in expanded mode
- **THEN** the sidebar displays the "ACA" badge and the text "AI Content Analyzer"

## ADDED Requirements

### Requirement: App Logo Assets

The application SHALL use a purple circuit-brain tree logo across all icon assets:

- The favicon (`icon.svg`) SHALL display the new circuit-brain tree logo.
- PWA icons (192x192, 512x512, and maskable variants) SHALL use the new logo.
- Apple touch icons SHALL use the new logo.

#### Scenario: Favicon displays new logo
- **WHEN** a user views the browser tab
- **THEN** the favicon shows the purple circuit-brain tree logo

#### Scenario: PWA install uses new icon
- **WHEN** a user installs the PWA
- **THEN** the home screen icon shows the purple circuit-brain tree logo

### Requirement: PWA and HTML Metadata

The application HTML and PWA manifest SHALL reflect the ACA brand:

- The HTML `<title>` SHALL be "ACA — AI Content Analyzer".
- The meta description SHALL describe AI-powered content analysis.
- The PWA manifest `name` SHALL be "ACA — AI Content Analyzer".
- The PWA manifest `short_name` SHALL be "ACA".
- The `apple-mobile-web-app-title` SHALL be "ACA".

#### Scenario: Browser tab shows correct title
- **WHEN** a user opens the application
- **THEN** the browser tab title reads "ACA — AI Content Analyzer"

#### Scenario: PWA manifest has correct names
- **WHEN** the PWA manifest is loaded
- **THEN** the name is "ACA — AI Content Analyzer" and the short name is "ACA"
