# Stuck-content sweeper and requeue CLI

> Parent roadmap: `ingestion-reliability`
> Change ID: `stuck-content-sweeper-and-requeue-cli`
> Effort: M
> Priority: 4

## Summary

Periodic job resetting PROCESSING/PARSING rows older than a timeout back to PARSED/PENDING and requeuing FAILED rows up to a retry budget (summarizer.py:90,276 never re-selects PROCESSING; queue/setup.py:590 fails jobs without resetting content status). Add 'aca manage requeue-stuck'.

## Dependencies

- None

## Acceptance Outcomes

- Content rows stuck >1h in transitional states trend to zero automatically
- FAILED rows are retried up to a budget and then surfaced, not stranded

## Rationale

PROCESSING/PARSING are unrecoverable black holes; FAILED has no retry path.
