# ph_ai_tracker — Data Pipeline Sprint Plan

## Scope

This sprint plan replaces the earlier package/scaffolding plan and targets the current class assignment architecture:

1. Save scraper output to SQLite.
2. Run scraper on a repeating cron schedule.
3. Containerize scraper + cron scheduler with Docker.
4. Persist SQLite data on a Docker volume.

Out of scope for this plan: API service layer.

---

## Sprint Sequence Overview

1. Sprint 1 — SQLite persistence foundation
2. Sprint 2 — Scheduled execution via cron
3. Sprint 3 — Docker containerization + persistent volume
4. Sprint 4 — Reliability, failure handling, and observability
5. Sprint 5 — Delivery documentation and runbook
6. Sprint 6 — Final demo hardening and submission packaging

---

## Sprint Dependencies

- Sprint 2 depends on Sprint 1 (scheduler needs write path).
- Sprint 3 depends on Sprint 2 (containerized schedule path).
- Sprint 4 depends on Sprints 1–3 (hardening full pipeline).
- Sprint 5 depends on Sprints 1–4 (document final behavior).
- Sprint 6 depends on all prior sprints.

---

## Definition of Done (Project-Level)

- Scraper writes structured data to SQLite consistently.
- Cron runs scraper repeatedly without manual intervention.
- Dockerized deployment persists SQLite data across restarts using a named volume.
- Tests cover positive and negative pipeline behavior.
- A new user can run the full pipeline from docs only.
