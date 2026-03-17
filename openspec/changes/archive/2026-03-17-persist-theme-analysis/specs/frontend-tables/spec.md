## ADDED Requirements

### Requirement: Themes page shows analysis history
The themes page SHALL display a list of past completed analyses below the current analysis, enabling users to browse historical analyses for temporal evolution tracking.

#### Scenario: History list renders with multiple analyses
- **WHEN** the themes page loads and multiple completed analyses exist
- **THEN** an "Analysis History" section SHALL display each past analysis with its date range, theme count, and relative time (e.g., "3 days ago")

#### Scenario: Empty history when only one analysis exists
- **WHEN** the themes page loads and only one analysis exists
- **THEN** no history section SHALL be displayed (the single analysis shows as the latest)

### Requirement: Past analysis viewable from history
Users SHALL be able to click a past analysis in the history list to view its full details (themes, scores, insights) in the main analysis card.

#### Scenario: Clicking history item loads past analysis
- **WHEN** a user clicks a past analysis in the history list
- **THEN** the main analysis card SHALL display that analysis's themes and metadata instead of the latest
