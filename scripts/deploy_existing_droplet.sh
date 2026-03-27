#!/usr/bin/env bash
set -euo pipefail

# One-command deploy helper for an existing DigitalOcean droplet.
# Usage:
#   bash scripts/deploy_existing_droplet.sh
# Optional env vars:
#   APP_DIR=/opt/ph-ai-tracker
#   REPO_URL=https://github.com/atg25/ProductHunt-Scraper.git
#   BRANCH=main
#   COMPOSE_PROJECT=phtracker
#   API_PORT=8000

APP_DIR="${APP_DIR:-/opt/ph-ai-tracker}"
REPO_URL="${REPO_URL:-https://github.com/atg25/ProductHunt-Scraper.git}"
BRANCH="${BRANCH:-main}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-phtracker}"
API_PORT="${API_PORT:-8000}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command '$1' is not installed" >&2
    exit 1
  }
}

need_cmd git
need_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  echo "error: docker compose plugin is required" >&2
  exit 1
fi

mkdir -p "${APP_DIR}"

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "[deploy] cloning repository into ${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"

echo "[deploy] updating repository"
git fetch origin
# Reset only tracked files in deployment directory to avoid stale deploy state.
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[deploy] created .env from .env.example"
fi

if ! grep -q '^PRODUCTHUNT_TOKEN=' .env; then
  echo 'PRODUCTHUNT_TOKEN=' >> .env
fi

if grep -q '^PRODUCTHUNT_TOKEN=$' .env || ! grep -q '^PRODUCTHUNT_TOKEN=[^[:space:]]' .env; then
  echo "error: PRODUCTHUNT_TOKEN is empty in ${APP_DIR}/.env" >&2
  echo "Set it before deploying, then rerun this script." >&2
  exit 1
fi

if [[ "${API_PORT}" == "8000" ]] && ss -ltn '( sport = :8000 )' | grep -q ':8000'; then
  API_PORT="8001"
  echo "[deploy] port 8000 is busy, switching API_PORT to ${API_PORT}"
fi

if grep -q '^API_PORT=' .env; then
  sed -i.bak "s/^API_PORT=.*/API_PORT=${API_PORT}/" .env && rm -f .env.bak
else
  printf '\nAPI_PORT=%s\n' "${API_PORT}" >> .env
fi

echo "[deploy] deploying compose project '${COMPOSE_PROJECT}'"
docker compose -p "${COMPOSE_PROJECT}" up -d --build

echo "[deploy] done"
echo "[deploy] health check URL: http://$(hostname -I | awk '{print $1}'):${API_PORT}/health"
echo "[deploy] view logs: docker compose -p ${COMPOSE_PROJECT} logs -f api scheduler"
