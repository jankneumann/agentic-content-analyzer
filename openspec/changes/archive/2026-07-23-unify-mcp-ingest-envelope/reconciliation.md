# Reconciliation: MCP ingest envelope

**Disposition**: Superseded; archive without implementation or spec sync.

The proposal requires synchronous `IngestionResponse` results from a monolithic
MCP server. The canonical architecture now registers typed ingestion tools in
`src/mcp_tools/ingestion.py`, submits durable work, and returns
`OperationHandle`. Files and pipeline submission follow the same contract.

RI-03's 86-test profile/MCP gate and the durable workflow contract tests verify
the governing behavior. The old tasks remain unchecked because implementing
them would restore an obsolete transport-specific result shape.
