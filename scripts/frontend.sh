#!/usr/bin/env bash
# Start Next.js dev server (port 3000).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env
if command -v pnpm >/dev/null 2>&1; then
  exec pnpm --filter web dev
else
  exec npx --yes pnpm@9.15.0 --filter web dev
fi
