# huggingface-papers-ingestion Specification

## Purpose

Define HuggingFace daily-paper discovery, extraction, deduplication, and
canonical durable workflow integration.

## Requirements

### Requirement: HuggingFace paper discovery and extraction

The system SHALL discover canonical arXiv paper links from configured
HuggingFace daily-paper pages, normalize versioned identifiers, enforce the
requested limit, and extract usable paper metadata/content.

#### Scenario: Daily paper page contains versioned duplicates

- **WHEN** discovery sees versioned and unversioned links for the same arXiv ID
- **THEN** it SHALL return one normalized paper candidate
- **AND** SHALL ignore non-paper links

#### Scenario: Paper page has usable metadata

- **WHEN** extraction finds title, authors, abstract, and arXiv identity
- **THEN** it SHALL produce structured content with HuggingFace and arXiv
  metadata
- **AND** SHALL reject content below the minimum usable threshold

### Requirement: HuggingFace paper deduplication

The ingestion service SHALL avoid duplicate HuggingFace rows and SHALL link a
HuggingFace record to an existing canonical arXiv record for the same paper.

#### Scenario: Paper already exists from arXiv

- **WHEN** the same normalized arXiv ID is discovered through HuggingFace
- **THEN** the HuggingFace record SHALL reference the existing canonical
  content
- **AND** repeated ingestion SHALL remain idempotent unless force reprocessing
  is requested

### Requirement: HuggingFace is a canonical source command

`huggingface_papers` SHALL be registered in the source capability registry,
typed command union, generated contracts, worker dispatch, CLI, HTTP, MCP, and
capability-driven frontend, and every mutation SHALL return a durable operation
handle.

#### Scenario: Agent submits HuggingFace ingestion through MCP

- **WHEN** the MCP source tool receives valid HuggingFace command fields
- **THEN** it SHALL submit the canonical typed command
- **AND** SHALL return an `OperationHandle` rather than an immediate ingestion
  result

#### Scenario: Frontend renders HuggingFace ingestion

- **WHEN** the frontend receives the HuggingFace capability descriptor
- **THEN** it SHALL render the source and accepted fields from that descriptor
- **AND** SHALL submit through the canonical ingestion endpoint
