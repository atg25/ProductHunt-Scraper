#!/usr/bin/env sh
set -eu

DB_PATH="${PH_AI_DB_PATH:-./data/ph_ai_tracker.db}"
STRATEGY="${PH_AI_TRACKER_STRATEGY:-scraper}"
SEARCH="${PH_AI_TRACKER_SEARCH:-AI}"
LIMIT="${PH_AI_TRACKER_LIMIT:-10}"

mkdir -p "$(dirname "$DB_PATH")"

echo "[demo] using db: $DB_PATH"
echo "[demo] first run"
poetry run ph-ai-tracker-runner --strategy "$STRATEGY" --search "$SEARCH" --limit "$LIMIT" --db-path "$DB_PATH" >/tmp/ph_ai_demo_run1.json

echo "[demo] second run"
poetry run ph-ai-tracker-runner --strategy "$STRATEGY" --search "$SEARCH" --limit "$LIMIT" --db-path "$DB_PATH" >/tmp/ph_ai_demo_run2.json

echo "[demo] verification"
sqlite3 "$DB_PATH" <<'SQL'
.headers on
.mode column
SELECT 'runs' AS table_name, COUNT(*) AS count FROM runs;
SELECT 'products' AS table_name, COUNT(*) AS count FROM products;
SELECT 'product_snapshots' AS table_name, COUNT(*) AS count FROM product_snapshots;
SELECT id, source, status, fetched_at, error FROM runs ORDER BY id DESC LIMIT 5;
SQL

echo "[demo] done"
