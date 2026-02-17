#!/usr/bin/env sh
set -eu

CRON_SCHEDULE="${CRON_SCHEDULE:-0 */6 * * *}"
TZ_VALUE="${TZ:-UTC}"

mkdir -p /var/log
mkdir -p /etc/cron.d

cat > /etc/cron.d/ph_ai_tracker <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=${TZ_VALUE}
${CRON_SCHEDULE} cd /app && ph-ai-tracker-runner --strategy "${PH_AI_TRACKER_STRATEGY:-scraper}" --search "${PH_AI_TRACKER_SEARCH:-AI}" --limit "${PH_AI_TRACKER_LIMIT:-20}" --db-path "${PH_AI_DB_PATH:-/data/ph_ai_tracker.db}" >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 /etc/cron.d/ph_ai_tracker
crontab /etc/cron.d/ph_ai_tracker

printf '[scheduler] starting cron with schedule: %s\n' "$CRON_SCHEDULE"

exec cron -f
