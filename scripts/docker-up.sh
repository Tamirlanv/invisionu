#!/usr/bin/env bash
# Build and start full stack (postgres, redis, api, web).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
exec docker compose up --build
