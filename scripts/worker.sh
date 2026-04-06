#!/usr/bin/env bash
# Redis BRPOP job worker (scaffold).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env

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

ensure_infra
export PYTHONPATH="$REPO_ROOT/apps/api/src"
# Local `make worker` should reflect production-critical media dependencies by default.
# Override with WORKER_REQUIRE_MEDIA_BINARIES=0 only for debugging non-video jobs.
: "${WORKER_REQUIRE_MEDIA_BINARIES:=1}"
export WORKER_REQUIRE_MEDIA_BINARIES
PY=$(api_python)
exec "$PY" "$REPO_ROOT/scripts/job_worker.py"
