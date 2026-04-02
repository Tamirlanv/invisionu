#!/usr/bin/env bash
# Start FastAPI with hot reload (port 8000).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
export PYTHONPATH="$REPO_ROOT/apps/api/src"

ensure_infra() {
  if command -v docker >/dev/null 2>&1; then
    echo "Ensuring local infra (postgres + redis) is running..."
    (cd "$REPO_ROOT" && docker compose up -d postgres redis >/dev/null) || {
      echo "Warning: failed to auto-start docker infra; continuing..." >&2
    }
  else
    echo "Warning: docker not found; skip infra auto-start." >&2
  fi
}

is_port_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

start_validation_service_if_needed() {
  local name="$1"
  local port="$2"
  if is_port_listening "$port"; then
    echo "$name already listening on :$port"
    return
  fi
  if ! command -v corepack >/dev/null 2>&1; then
    echo "Warning: corepack not found; cannot auto-start $name" >&2
    return
  fi
  echo "Starting $name on :$port in background..."
  (
    cd "$REPO_ROOT"
    nohup corepack pnpm --filter "$name" dev >"/tmp/${name}.log" 2>&1 &
  )
}

ensure_infra
start_validation_service_if_needed "video-validation" 4300
start_validation_service_if_needed "certificate-validation" 4400
start_validation_service_if_needed "candidate-validation-orchestrator" 4500

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg is not installed (video/certificate pipelines may fail)." >&2
fi
if ! command -v tesseract >/dev/null 2>&1; then
  echo "Warning: tesseract is not installed (certificate OCR may fail)." >&2
fi

PY=$(api_python)
if [[ "$PY" == "python3" ]] && [[ ! -d "$REPO_ROOT/apps/api/.venv" ]]; then
  echo "Create venv first: make install-api" >&2
  exit 1
fi
echo "Applying migrations (alembic upgrade head)..."
(
  cd "$REPO_ROOT/apps/api"
  "$PY" -m alembic upgrade head
) || {
  echo "Migration step failed; aborting backend start." >&2
  exit 1
}
echo "Tip: run 'make seed' once for roles + internal test questions (commission user is ensured on API startup from env)."
cd "$REPO_ROOT/apps/api"
exec "$PY" -m uvicorn invision_api.main:app --reload --host 0.0.0.0 --port 8000
