## ADDED Requirements

### Requirement: Digest-bound podcast provenance

Podcast script generation SHALL load available content exclusively from the persisted digest source content IDs and summary IDs. It MUST NOT re-query all completed content by digest period. Content retrieval tools SHALL reject IDs outside the available set, and every stored citation MUST be a member of that set.

#### Scenario: Source-filtered digest constrains script context
- **GIVEN** a digest was generated from only RSS and Gmail content
- **WHEN** a podcast script is generated from that digest
- **THEN** the script's available IDs exactly equal the digest source content IDs
- **AND** content from all other sources is unavailable to generation tools

#### Scenario: Tool fetch is provenance constrained
- **WHEN** the model requests content absent from the digest source IDs
- **THEN** the tool returns a typed provenance rejection
- **AND** the rejected ID is not persisted as fetched or cited

### Requirement: Durable podcast workflows

Podcast script generation and podcast audio generation SHALL run as PostgreSQL operations through application workflow services. Script and podcast records MUST be created and linked to their operations before completion is reported.

#### Scenario: Script operation returns persisted script
- **WHEN** script generation completes successfully
- **THEN** the operation resource identifies a persisted `PodcastScriptRecord`
- **AND** the record stores the digest fingerprint, available IDs, and cited IDs

#### Scenario: Audio operation uses approved persisted script
- **WHEN** podcast audio generation is submitted for an approved script
- **THEN** the queue handler calls the public podcast audio workflow
- **AND** the completed operation identifies a persisted `Podcast` with stored audio

#### Scenario: Interface cannot bypass script approval
- **WHEN** any interface submits podcast audio for an unapproved script
- **THEN** submission fails with the same validation problem
- **AND** no audio job or podcast record is created
