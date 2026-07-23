# Contracts: reconcile-openspec-inventory

This change does not alter runtime API, event, database, or generated client
contracts. Its executable contract is the final-state inventory disposition
snapshot validated against active and archived OpenSpec directories in
transitional and post-archive modes.

The canonical durable workflow contracts under
`openspec/contracts/content-workflows/` remain unchanged.
