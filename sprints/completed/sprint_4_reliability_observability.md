# Sprint 4 — Reliability and Observability

## Sprint Goal

Make the pipeline resilient to transient failures and observable for debugging.

## Backlog / Tasks

- Add run status tracking (`success`, `partial`, `failure`) with error detail fields.
- Implement retry/backoff for transient HTTP/network failures.
- Ensure transactional safety and rollback on persistence errors.
- Add constraints and canonicalization rules for dedupe consistency.
- Add tests for timeout, bad response, DB lock, and scheduler continuation after errors.
- Add summary counters in logs (fetched, inserted, updated, failed).

## Acceptance Criteria

- Failed runs are recorded with clear error metadata.
- Scheduler continues operating after recoverable and non-recoverable run failures.
- Duplicate entities are constrained and/or upserted deterministically.
- Reliability-focused tests pass in CI.
