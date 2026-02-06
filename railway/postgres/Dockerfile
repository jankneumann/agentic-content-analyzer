#############################################
# Stage 1: Builder - compile all extensions
#############################################
FROM postgres:16-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    postgresql-server-dev-16 \
    libssl-dev \
    libclang-dev \
    clang \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for pg_search and pgmq)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install pgrx (PostgreSQL extension framework)
# Using pgrx 0.12.6 which is compatible with pg_search and pgmq
RUN cargo install --locked cargo-pgrx@0.12.6 \
    && cargo pgrx init --pg16 $(which pg_config)

# Install pgvector (C-based, simple compilation)
RUN cd /tmp \
    && git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make OPTFLAGS="" \
    && make install \
    && rm -rf /tmp/pgvector

# Install pg_cron (C-based, simple compilation)
RUN cd /tmp \
    && git clone --branch v1.6.4 https://github.com/citusdata/pg_cron.git \
    && cd pg_cron \
    && make \
    && make install \
    && rm -rf /tmp/pg_cron

# Install pgmq (Rust-based via pgrx)
RUN cd /tmp \
    && git clone --branch v1.4.4 https://github.com/tembo-io/pgmq.git \
    && cd pgmq/pgmq-extension \
    && cargo pgrx install --release --pg-config $(which pg_config) \
    && rm -rf /tmp/pgmq

# Install pg_search (ParadeDB - Rust-based via pgrx)
# Note: pg_search requires specific build flags
RUN cd /tmp \
    && git clone --branch v0.13.0 https://github.com/paradedb/paradedb.git \
    && cd paradedb/pg_search \
    && cargo pgrx install --release --pg-config $(which pg_config) \
    && rm -rf /tmp/paradedb

#############################################
# Stage 2: Runtime - minimal production image
#############################################
FROM postgres:16-bookworm

# Copy compiled extensions from builder
COPY --from=builder /usr/share/postgresql/16/extension/ /usr/share/postgresql/16/extension/
COPY --from=builder /usr/lib/postgresql/16/lib/ /usr/lib/postgresql/16/lib/

# Copy optimized PostgreSQL configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf

# Initialization script to create extensions
COPY init-extensions.sql /docker-entrypoint-initdb.d/

# Health check for Railway monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pg_isready -U postgres || exit 1

# Expose PostgreSQL port
EXPOSE 5432

# Use custom config file
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
