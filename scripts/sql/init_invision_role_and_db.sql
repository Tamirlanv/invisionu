-- Optional manual run (superuser), same defaults as docker-compose:
--   psql -d postgres -f scripts/sql/init_invision_role_and_db.sql
-- Prefer: make init-db

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'invision') THEN
    CREATE ROLE invision WITH LOGIN PASSWORD 'invision';
  END IF;
END
$$;

-- Run only if the database is not created yet (duplicate → ignore error):
-- CREATE DATABASE invision OWNER invision;
