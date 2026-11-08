#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$MEDFLOCK_DB_PASSWORD" <<'SQL'
CREATE ROLE medflock LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE medflock TO medflock;
GRANT USAGE, CREATE ON SCHEMA public TO medflock;
SQL
