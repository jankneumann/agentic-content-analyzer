## ADDED Requirements

### Requirement: File Sync Never Copies Browser Profiles

File storage sync SHALL refuse every file reference that would read from or write
into a browser-profile directory. That means a reference whose path contains
`.aca/browser-profiles`, or whose resolved local path on the source or the target
falls inside the configured `browser_profiles_dir`. Refused references SHALL be
counted as `excluded` in the sync statistics and SHALL NOT be copied, including in
dry-run previews.

#### Scenario: Local source bucket rooted at a home directory
- **GIVEN** a local source bucket whose root contains a populated `.aca/browser-profiles/<site>/` directory
- **AND** a database row referencing a file inside it
- **WHEN** `aca sync push` runs file sync
- **THEN** that file SHALL NOT be copied to the target
- **AND** the sync statistics SHALL report it as `excluded`
- **AND** other referenced files SHALL still be copied

#### Scenario: Target bucket contains the profiles root
- **GIVEN** a local target bucket whose root contains the configured `browser_profiles_dir`
- **WHEN** file sync processes a reference that resolves inside it
- **THEN** nothing SHALL be written into the profiles directory

#### Scenario: Dry run reports exclusions
- **WHEN** file sync runs with `--dry-run` and a reference points into a browser-profile directory
- **THEN** the reference SHALL be counted as `excluded` and not as `would_copy`
