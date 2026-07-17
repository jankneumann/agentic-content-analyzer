# content-provenance Specification

## Purpose
TBD - created by archiving change unify-content-workflows-agentic-surfaces. Update Purpose after archive.
## Requirements
### Requirement: Canonical summary-backed content set

Workflow content resolution SHALL return one immutable `ResolvedContentSet` containing ordered canonical content IDs, corresponding persisted summary IDs, a normalized selection policy, grouped exclusions, and a deterministic fingerprint. A content alias with `canonical_id` MUST NOT contribute an independent item, and a canonical content record without a persisted summary MUST NOT be eligible for theme, digest, or podcast workflows.

#### Scenario: Duplicate aliases resolve once
- **GIVEN** a canonical content record and multiple completed alias records point to it
- **WHEN** a workflow content set is resolved
- **THEN** the canonical content ID appears exactly once
- **AND** the aliases are reported with exclusion reason `duplicate_alias`

#### Scenario: Missing summary is excluded
- **GIVEN** a completed canonical content record has no persisted summary
- **WHEN** a workflow content set is resolved
- **THEN** the content is absent from the eligible items
- **AND** it is reported with exclusion reason `missing_summary`

### Requirement: Explicit half-open date policy

Workflow selection SHALL default to `date_basis=published_date` and SHALL include records where `start <= published_date < end`. Null publication dates MUST be excluded under this default. `date_basis=ingested_at` SHALL be used only when explicitly requested.

#### Scenario: Adjacent periods do not overlap
- **GIVEN** content is published exactly at a period end
- **WHEN** adjacent workflow periods are resolved
- **THEN** the content is excluded from the earlier period
- **AND** it is included in the later period

#### Scenario: Explicit ingestion date basis
- **GIVEN** content has no publication date and has an ingestion date inside the period
- **WHEN** the caller explicitly selects `date_basis=ingested_at`
- **THEN** the content is eligible if all other workflow conditions are satisfied

### Requirement: End-to-end provenance invariants

Themes, digests, podcast scripts, citations, and audio workflows SHALL preserve the resolved set supplied to the digest workflow. Theme content IDs MUST be a subset of digest source content IDs; podcast available IDs MUST equal digest source content IDs; cited IDs MUST be a subset of available IDs; and the digest count MUST equal the unique eligible canonical content count.

#### Scenario: Filtered digest constrains themes and podcast
- **WHEN** a digest is created from a source-filtered resolved content set
- **THEN** theme analysis receives only that resolved set
- **AND** the podcast script exposes only the persisted digest source IDs
- **AND** no excluded source can be fetched or cited by the script generator

#### Scenario: Citation outside digest is rejected
- **WHEN** a podcast tool or model attempts to cite a content ID absent from the digest source IDs
- **THEN** the citation is rejected
- **AND** the workflow records a provenance violation without adding the ID to the script

### Requirement: Persisted selection snapshot

Every newly created digest SHALL persist source content IDs, source summary IDs, normalized selection policy, and selection fingerprint. Every podcast script SHALL persist the same fingerprint and its available and cited content IDs. Script generation MUST fail with a typed provenance error if the digest snapshot is incomplete or inconsistent.

#### Scenario: Digest and script fingerprints match
- **WHEN** a podcast script is generated from a current digest
- **THEN** the script selection fingerprint equals the digest selection fingerprint
- **AND** the script's available content IDs equal the digest source content IDs

#### Scenario: Legacy incomplete digest is explicit
- **GIVEN** a legacy digest cannot provide complete source provenance
- **WHEN** podcast generation is requested
- **THEN** the operation fails with a problem identifying the digest as `legacy-v0`
- **AND** the system does not re-query the digest period as a fallback
