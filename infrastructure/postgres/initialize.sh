#!/bin/sh
set -eu
# This entrypoint runs only for a new PostgreSQL volume. Never reset existing data.
app_password="$(cat /run/secrets/postgres_app_password)"
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set app_password="$app_password" <<'SQL'
CREATE ROLE relayn LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'app_password';
CREATE DATABASE relayn OWNER relayn;
REVOKE ALL ON DATABASE relayn FROM PUBLIC;
SQL
unset app_password
