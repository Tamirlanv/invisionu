#!/usr/bin/env bash
# Run Alembic migrations against DATABASE_URL from .env
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"
cd "$REPO_ROOT/apps/api"
PY=$(api_python)
exec "$PY" -m alembic upgrade head
