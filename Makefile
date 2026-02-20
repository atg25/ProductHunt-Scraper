BUNDLE_FILE := codebase_review_bundle.txt

.PHONY: test run runner demo db-tables db-verify docker-build docker-up docker-down docker-logs bundle

test:
	poetry run pytest

run:
	poetry run ph-ai-tracker --strategy scraper --search AI --limit 10

runner:
	poetry run ph-ai-tracker-runner --strategy scraper --search AI --limit 20 --db-path $${PH_AI_DB_PATH:-./data/ph_ai_tracker.db}

demo:
	sh scripts/demo_pipeline.sh

db-tables:
	sqlite3 $${PH_AI_DB_PATH:-./data/ph_ai_tracker.db} ".tables"

db-verify:
	sqlite3 $${PH_AI_DB_PATH:-./data/ph_ai_tracker.db} < scripts/sql/verify_pipeline.sql

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f scheduler

bundle:
	@echo "Building Uncle Bob review bundle…"
	@.venv/bin/python scripts/build_bundle.py --out $(BUNDLE_FILE)
