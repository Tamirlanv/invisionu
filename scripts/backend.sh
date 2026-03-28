#!/usr/bin/env bash
# Start FastAPI with hot reload (port 8000).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"
cd "$REPO_ROOT/apps/api"
PY=$(api_python)
if [[ "$PY" == "python3" ]] && [[ ! -d "$REPO_ROOT/apps/api/.venv" ]]; then
  echo "Create venv first: make install-api" >&2
  exit 1
fi
exec "$PY" -m uvicorn invision_api.main:app --reload --host 0.0.0.0 --port 8000
