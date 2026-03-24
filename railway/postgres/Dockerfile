#############################################
# Railway PostgreSQL Image
#############################################
# Previously: multi-stage build compiling pgvector, pg_search, pg_cron,
# and pgmq from source (~20min build time).
#
# Now: ParadeDB includes all required extensions pre-built:
#   - pgvector 0.8.1 (vector similarity search)
#   - pg_search 0.22.2 (BM25 full-text search)
#   - pg_cron 1.6 (scheduled jobs)
#   - pg_ivm 1.13 (incremental materialized views)
#   - PostGIS 3.6.2 (geospatial)
#
# Custom postgresql.conf and init scripts are still applied.
#############################################
FROM paradedb/paradedb:0.22.2-pg17

# Copy custom PostgreSQL configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf

# Copy initialization scripts
COPY init-extensions.sql /docker-entrypoint-initdb.d/01-init-extensions.sql
COPY init-backup-job.sql /docker-entrypoint-initdb.d/02-init-backup-job.sql
COPY 00-set-backup-gucs.sh /docker-entrypoint-initdb.d/00-set-backup-gucs.sh

# Use custom config
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
