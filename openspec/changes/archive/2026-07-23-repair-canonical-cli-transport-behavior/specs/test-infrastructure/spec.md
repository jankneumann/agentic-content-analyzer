## ADDED Requirements

### Requirement: Hermetic CLI transport tests

CLI unit tests MUST select external transports explicitly and MUST consume
coroutines passed across mocked sync/async boundaries.

#### Scenario: Ambient credentials do not select a live transport

- **GIVEN** a developer environment contains YouTube API credentials
- **WHEN** the RSS curation unit tests run
- **THEN** the tests explicitly select the RSS transport
- **AND** no YouTube Data API request is made

#### Scenario: Async graph boundary is consumed

- **WHEN** the graph extraction CLI unit test exercises the synchronous adapter
- **THEN** the extraction coroutine is awaited to completion
- **AND** the CLI suite emits no unawaited-coroutine warning

### Requirement: CLI dependency warning hygiene

The default CLI environment MUST use dependency versions and tracked profile
keys that do not emit known compatibility or migration warnings during normal
startup.

#### Scenario: Optional crawler dependencies are compatible

- **WHEN** the Crawl4AI optional dependency set is installed from the lock
- **THEN** its character detector version is supported by the installed Requests version

#### Scenario: Tracked local profile uses canonical graph keys

- **WHEN** the tracked local profile is loaded
- **THEN** it uses canonical `neo4j_uri`, `neo4j_user`, and `neo4j_password` keys
- **AND** no legacy Neo4j-key migration warning is emitted for that profile
