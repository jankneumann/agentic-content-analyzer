## ADDED Requirements

### Requirement: YouTube item outcomes are truthful and correlated

Every selected video SHALL produce one correlated item outcome using the shared outcome/error vocabulary. Exceptions caught to preserve playlist or batch continuation SHALL increment failed counts and emit detailed exception evidence; they SHALL NOT be returned as successful skips.

#### Scenario: [YT-001] Video processor catches provider exception

- **WHEN** transcript, metadata, download, keyframe, model, or persistence processing raises an exception for one video
- **THEN** the item is classified retryable or permanent failure by policy
- **AND** aggregate failed counts include it
- **AND** the remaining eligible videos continue

#### Scenario: [YT-002] Video is intentionally filtered

- **WHEN** duration, age, duplicate, or configured length policy excludes a video
- **THEN** the item is classified with the matching non-error outcome
- **AND** the trace records the policy code without an exception stack

#### Scenario: [YT-003] Single video fails

- **WHEN** a single-video operation encounters a processing exception
- **THEN** its domain outcome is failed rather than ok-with-skip
- **AND** the exact operation exposes bounded stage/error codes and trace correlation
