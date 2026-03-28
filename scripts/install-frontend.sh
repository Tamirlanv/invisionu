#!/usr/bin/env bash
# Install Node dependencies (pnpm workspace).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
if command -v pnpm >/dev/null 2>&1; then
  exec pnpm install
else
  exec npx --yes pnpm@9.15.0 install
fi
