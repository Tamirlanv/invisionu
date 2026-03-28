#!/usr/bin/env bash
# Source from scripts/*.sh after setting REPO_ROOT:
#   REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
#   # shellcheck source=scripts/lib/common.sh
#   source "$REPO_ROOT/scripts/lib/common.sh"
set -euo pipefail

load_env() {
  local f="${1:-${REPO_ROOT:-}/.env}"
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
}

api_python() {
  local py="${REPO_ROOT:-}/apps/api/.venv/bin/python"
  if [[ -x "$py" ]]; then
    echo "$py"
  else
    echo "python3"
  fi
}
