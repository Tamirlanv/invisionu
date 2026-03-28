#!/usr/bin/env bash
# Create role + database on PostgreSQL at localhost (matches POSTGRES_* in .env).
# Use when: FATAL: role "invision" does not exist
# (often Homebrew Postgres on :5432 instead of Docker.)
set -eo pipefail
# Note: no `set -u` — empty psql arg arrays + bash 3.2/5.x differ on "${arr[@]}".

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"
cd "$REPO_ROOT"
load_env

POSTGRES_USER="${POSTGRES_USER:-invision}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-invision}"
POSTGRES_DB="${POSTGRES_DB:-invision}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Install PostgreSQL client, or use Docker DB only: make infra" >&2
  exit 1
fi

sql_create_role() {
  POSTGRES_USER="$POSTGRES_USER" POSTGRES_PASSWORD="$POSTGRES_PASSWORD" python3 <<'PY'
import os
u = os.environ["POSTGRES_USER"]
p = os.environ["POSTGRES_PASSWORD"].replace("'", "''")
print(
    f"""DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{u}') THEN
    CREATE ROLE {u} WITH LOGIN PASSWORD '{p}';
  END IF;
END
$$;"""
)
PY
}

create_all() {
  # shellcheck disable=SC2068
  if [[ $# -eq 0 ]]; then
    sql_create_role | psql -v ON_ERROR_STOP=1 -d postgres -f /dev/stdin
    if ! psql -v ON_ERROR_STOP=1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'" | grep -q 1; then
      psql -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
    fi
  else
    sql_create_role | psql "$@" -v ON_ERROR_STOP=1 -d postgres -f /dev/stdin
    if ! psql "$@" -v ON_ERROR_STOP=1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'" | grep -q 1; then
      psql "$@" -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
    fi
  fi
}

if psql -d postgres -c "SELECT 1" >/dev/null 2>&1; then
  echo "Connecting as default superuser (peer/local)…"
  create_all
  echo "OK: role ${POSTGRES_USER} and database ${POSTGRES_DB} are ready. Run: make migrate"
  exit 0
fi

export PGPASSWORD="${PGPASSWORD:-postgres}"
if psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1; then
  echo "Connecting as postgres@127.0.0.1…"
  create_all -h 127.0.0.1 -p 5432 -U postgres
  echo "OK: role ${POSTGRES_USER} and database ${POSTGRES_DB} are ready. Run: make migrate"
  exit 0
fi

echo "Could not connect as a superuser to PostgreSQL." >&2
echo "" >&2
echo "Common fix: port 5432 is not Docker. Either:" >&2
echo "  1) Stop local Postgres (e.g. brew services stop postgresql@16), then: make infra && make migrate" >&2
echo "  2) Or create role manually as superuser, then: make migrate" >&2
echo "  3) Or set DATABASE_URL to a user that already exists on your server." >&2
exit 1
