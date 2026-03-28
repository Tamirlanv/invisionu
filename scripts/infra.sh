#!/usr/bin/env bash
# Start Postgres + Redis in Docker (detached).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
exec docker compose up -d postgres redis
