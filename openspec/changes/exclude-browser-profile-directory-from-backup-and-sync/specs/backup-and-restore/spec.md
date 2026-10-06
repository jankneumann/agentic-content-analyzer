## ADDED Requirements

### Requirement: Browser Profile Directories Are Never Backed Up

The system SHALL exclude every persistent browser-profile directory from every
backup artifact. That means the configured `browser_profiles_dir` (default
`~/.aca/browser-profiles`) and any `.aca/browser-profiles` directory wherever it
appears. These directories hold live session credentials. The exclusion SHALL be
applied inside the artifacts `tar` invocation without a shell. It SHALL be
computed from resolved paths, so a configured artifact directory that contains the
profiles root still excludes it.

#### Scenario: Artifact directory contains the default profile layout
- **GIVEN** an artifact storage path that points at a home directory containing a populated `.aca/browser-profiles/<site>/` directory
- **WHEN** `aca backup run` builds and streams the artifacts tarball
- **THEN** no member of `artifacts.tar` SHALL be inside the browser-profiles directory
- **AND** every other file in that artifact directory SHALL still be captured

#### Scenario: Configured profiles root under an artifact directory
- **GIVEN** `browser_profiles_dir` points at a populated directory nested inside an artifact directory, under a name that does not match the default layout
- **WHEN** the artifacts tarball is built
- **THEN** that directory SHALL be excluded by an anchored, non-wildcard exclusion placed before the `tar` operands
- **AND** a sibling directory sharing its name as a prefix SHALL still be captured

#### Scenario: Artifact directory inside the profiles root
- **GIVEN** an artifact storage path that resolves to the profiles root or a directory inside it
- **WHEN** the artifacts store is planned
- **THEN** that directory SHALL NOT be passed to `tar`
- **AND** when no other artifact directory remains, the store SHALL be skipped with reason `no_artifact_directories_present`

#### Scenario: Backup documentation lists the exclusion
- **WHEN** an operator reads `docs/BACKUP_RESTORE.md`
- **THEN** it SHALL list `~/.aca/browser-profiles/` as an excluded path and state why
