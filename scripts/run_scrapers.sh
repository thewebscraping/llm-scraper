#!/bin/zsh
# Lightweight wrapper to trigger scraping wave manually (outside Celery Beat)
# Usage:
#   ./scripts/run_scrapers.sh            # all domains
#   DOMAIN=cryptoslate.com ./scripts/run_scrapers.sh   # single domain
# Requires: REDIS_URL set (or .env sourced) and virtualenv activated.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/*}"
cd "$PROJECT_ROOT"

if [ -f .env ]; then
  source .env
fi

DOMAIN_ARG=""
if [ -n "${DOMAIN:-}" ]; then
  DOMAIN_ARG="--domain $DOMAIN"
fi

python scripts/trigger_scrapes.py $DOMAIN_ARG
