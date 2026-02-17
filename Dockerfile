FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.3.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock README.md /app/
COPY src /app/src
COPY scripts /app/scripts

RUN poetry config virtualenvs.create false \
    && poetry install --only main \
    && chmod +x /app/scripts/cron/entrypoint.sh \
    && mkdir -p /data

ENV PH_AI_DB_PATH=/data/ph_ai_tracker.db \
    CRON_SCHEDULE="0 */6 * * *" \
    PH_AI_TRACKER_STRATEGY=scraper \
    PH_AI_TRACKER_SEARCH=AI \
    PH_AI_TRACKER_LIMIT=20 \
    TZ=UTC

VOLUME ["/data"]

ENTRYPOINT ["/app/scripts/cron/entrypoint.sh"]
