# notification-events Specification Delta

## ADDED Requirements

### Requirement: External alerts are isolated from generic notifications

Out-of-band workflow alerts SHALL use the closed terminal-event and delivery
contracts rather than generic notification title, summary, payload, SSE queues,
or device-registration records. Existing in-app notifications MAY continue for
compatibility but SHALL NOT be treated as proof of external delivery.

#### Scenario: A generic notification contains unsafe fields

- **WHEN** an in-app notification contains a raw error, natural source key, or
  arbitrary URL
- **THEN** those fields SHALL NOT be copied into a workflow alert envelope

#### Scenario: No SSE subscriber is connected

- **WHEN** an alert-eligible terminal event is committed without SSE subscribers
- **THEN** durable external delivery SHALL remain eligible and recoverable
