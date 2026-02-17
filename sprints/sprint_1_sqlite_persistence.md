# Sprint 1 — SQLite Persistence Foundation

## Sprint Goal

Integrate SQLite persistence so each scraper execution stores durable run and product data.

## Backlog / Tasks

- Design relational schema for run tracking and product history.
- Add SQLite bootstrap/init logic for table creation.
- Implement data access layer (insert run, upsert product, insert snapshot).
- Wire scraper run path to persist results in a transaction.
- Add DB configuration via environment variable (`DB_PATH`).
- Add tests for schema creation, successful writes, and dedupe/upsert behavior.

## Acceptance Criteria

- Running one scraper cycle creates the database file and required tables.
- A run record and related product data are written for each execution.
- Repeated runs do not create duplicate product entities for same canonical key.
- SQLite persistence tests pass in CI.
