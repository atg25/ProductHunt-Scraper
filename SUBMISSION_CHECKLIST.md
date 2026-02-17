# Submission Checklist

## Pre-Submission Validation

- [ ] `poetry run pytest` passes
- [ ] Local one-shot run writes to SQLite
- [ ] Docker scheduler starts successfully
- [ ] Cron execution appears in container logs
- [ ] Data persists across container restart
- [ ] Requirement traceability document reviewed

## Commands

### 1) Test suite

```bash
poetry run pytest
```

### 2) Local pipeline run

```bash
poetry run ph-ai-tracker-runner --strategy scraper --search AI --limit 10 --db-path ./data/ph_ai_tracker.db
```

### 3) Verify DB data

```bash
sqlite3 ./data/ph_ai_tracker.db < scripts/sql/verify_pipeline.sql
```

### 4) Docker scheduler

```bash
docker compose up -d --build
docker compose logs -f scheduler
```

### 5) Persistence check

```bash
docker compose down
docker compose up -d
docker compose exec scheduler sh -lc "python - <<'PY'
import sqlite3
conn = sqlite3.connect('/data/ph_ai_tracker.db')
print(conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0])
conn.close()
PY"
```

## Deliverables

- [ ] Source code pushed to GitHub
- [ ] Sprint docs updated in `sprints/`
- [ ] `RUNBOOK.md` included
- [ ] `REQUIREMENTS_TRACEABILITY.md` included
- [ ] `SUBMISSION_CHECKLIST.md` included
