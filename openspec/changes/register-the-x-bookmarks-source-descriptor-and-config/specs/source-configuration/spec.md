## ADDED Requirements

### Requirement: X bookmarks source configuration

The source configuration SHALL support an `x_bookmarks` source type through an
`XBookmarksSource` model in the `Source` union, with `expand_links` (boolean,
default false) and `max_entries` (integer 1 to 10000, optional), and
`SourcesConfig.get_x_bookmarks_sources()` SHALL return only enabled entries.
The model SHALL NOT carry any credential. Because it reads the bookmarks of
the one account whose session is configured, every `x_bookmarks` entry SHALL
have the natural key `x_bookmarks:account` regardless of its `name`. The
repository SHALL ship `sources.d/x_bookmarks.yaml` with exactly one entry that
is disabled by default and whose comment names the `aca auth session x`
command and the `X_AUTH_TOKEN` and `X_CT0` credentials.

#### Scenario: Renaming keeps the source identity

- **WHEN** `source_key()` is computed for two `x_bookmarks` entries named differently
- **THEN** both return `x_bookmarks:account`, so a database override matches the YAML entry

#### Scenario: Fresh install does not plan the source

- **WHEN** the shipped `sources.d` directory is loaded and the registry plans the scheduled commands
- **THEN** the `x_bookmarks` entry is present with `enabled: false` and no `x_bookmarks` command is planned

#### Scenario: Out-of-range bound is rejected

- **WHEN** an `x_bookmarks` entry sets `max_entries` to 0 or 10001
- **THEN** source validation fails
