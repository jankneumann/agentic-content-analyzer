# Contract scope

This change proposes additive typed ingestion/history contracts plus one
intentional summary-only narrowing of generic operation list rows in
`openapi/v1.yaml`. During implementation it is merged into
`openspec/contracts/content-workflows/openapi/v1.yaml`, then the existing
Python and TypeScript workflow models are regenerated.

No new database table or event contract applies:

- `pgqueuer_jobs` remains the authoritative persistence contract.
- an index migration is permitted only if task 4.7 records a query plan proving
  the existing indexes insufficient;
- retention changes query/delete existing queue rows and add no state machine;
- RI-09 owns notification/telemetry events.
