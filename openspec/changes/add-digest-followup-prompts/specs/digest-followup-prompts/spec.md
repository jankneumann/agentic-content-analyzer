## ADDED Requirements

### Requirement: Follow-Up Prompt Generation

The system SHALL generate follow-up prompts for each digest section during digest creation.

#### Scenario: Prompts generated per section

- **GIVEN** a digest is being created (daily or weekly)
- **WHEN** the LLM generates strategic insights, technical developments, or emerging trends
- **THEN** each section SHALL include 2-3 `followup_prompts`
- **AND** each prompt SHALL be self-contained (includes enough context to use without the full digest)
- **AND** each prompt SHALL reference specific technologies, patterns, or trends from that section

#### Scenario: Prompts are action-oriented

- **GIVEN** a generated follow-up prompt
- **THEN** the prompt SHALL ask the LLM to perform a concrete task: analyze implications, compare alternatives, generate implementation plans, evaluate risks, or draft a brief
- **AND** the prompt SHALL assume a technical leader or senior engineer audience

#### Scenario: Configurable prompt count

- **GIVEN** a `DigestRequest` with `max_followup_prompts=2`
- **WHEN** a digest is created
- **THEN** each section SHALL contain at most 2 follow-up prompts

#### Scenario: Default prompt count

- **GIVEN** a `DigestRequest` without `max_followup_prompts`
- **WHEN** a digest is created
- **THEN** each section SHALL contain at most 3 follow-up prompts

#### Scenario: Backward compatibility

- **GIVEN** an existing digest created before this feature
- **WHEN** the digest is loaded from the database
- **THEN** `followup_prompts` SHALL default to an empty list
- **AND** no error SHALL occur

### Requirement: Follow-Up Prompts in Markdown Output

The system SHALL include follow-up prompts in the digest markdown representation.

#### Scenario: Collapsible prompts in markdown

- **GIVEN** a digest section with follow-up prompts
- **WHEN** markdown content is generated
- **THEN** prompts SHALL appear after the section content in a `<details>` block
- **AND** the summary text SHALL indicate the number of prompts

#### Scenario: Section without prompts

- **GIVEN** a digest section with no follow-up prompts (empty list)
- **WHEN** markdown content is generated
- **THEN** no `<details>` block SHALL be rendered for that section

### Requirement: Follow-Up Prompts in Shared View

The system SHALL display follow-up prompts when a digest is shared via public link.

#### Scenario: Shared digest includes prompts

- **GIVEN** a digest with follow-up prompts is shared via `/shared/digest/{token}`
- **WHEN** the HTML page is rendered from `markdown_html`
- **THEN** the `<details>` blocks SHALL render as collapsible sections
- **AND** prompts SHALL be visible when expanded

### Requirement: Follow-Up Prompts in Review UI

The system SHALL display follow-up prompts in the digest review interface with copy functionality.

#### Scenario: Prompts displayed in DigestPane

- **GIVEN** a digest with follow-up prompts
- **WHEN** viewed in the review UI
- **THEN** each section SHALL show a collapsible "Follow-up prompts" area
- **AND** each prompt SHALL have a copy-to-clipboard button

#### Scenario: Copy prompt to clipboard

- **GIVEN** a follow-up prompt displayed in the review UI
- **WHEN** the user clicks the copy button
- **THEN** the prompt text SHALL be copied to the system clipboard
- **AND** visual feedback SHALL confirm the copy action

## MODIFIED Requirements

### Requirement: Digest Creation Output Schema (from pipeline spec)

The digest creation LLM output schema SHALL include `followup_prompts` in each section type.

#### Scenario: Updated JSON output format

- **GIVEN** the digest creation prompt
- **WHEN** the LLM generates a response
- **THEN** each object in `strategic_insights`, `technical_developments`, and `emerging_trends` arrays SHALL include a `followup_prompts` field
- **AND** the field SHALL be a JSON array of strings
