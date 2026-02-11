#!/bin/bash
# Create the default test database on first container start.
# Worktree-specific databases are created dynamically by pytest fixtures.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE newsletters_test OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'newsletters_test')
\gexec
EOSQL
