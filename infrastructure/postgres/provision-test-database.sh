#!/bin/sh
set -eu
# Run inside the existing Compose postgres container; never print credentials.
export PGPASSWORD="$(cat /run/secrets/postgres_admin_password)"
psql -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE DATABASE test_relayn OWNER relayn'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'test_relayn')
\gexec
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = 'test_relayn' AND r.rolname = 'relayn'
    ) THEN
        RAISE EXCEPTION 'Existing test_relayn must be owned by relayn; refusing to alter it';
    END IF;
    IF EXISTS (
        SELECT FROM pg_roles WHERE rolname = 'relayn'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'relayn has unexpected elevated privileges';
    END IF;
END $$;
REVOKE ALL ON DATABASE test_relayn FROM PUBLIC;
SQL
unset PGPASSWORD
