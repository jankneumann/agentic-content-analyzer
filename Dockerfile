# Multi-stage Dockerfile for Newsletter Aggregator API
# Supports both web API and worker services

# ============================================
# Stage 1: Build dependencies
# ============================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir --root-user-action=ignore uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
# Using --frozen to ensure reproducible builds
RUN uv sync --frozen --no-dev --no-editable

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim as runtime

WORKDIR /app

# Install runtime dependencies (DEBIAN_FRONTEND suppresses interactive prompts)
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy and set up entrypoint script
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Default port (Railway sets PORT env var dynamically)
ENV PORT=8000
EXPOSE 8000

# Health check - uses PORT env var for flexibility
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; import httpx; httpx.get(f'http://localhost:{os.environ.get(\"PORT\", 8000)}/health').raise_for_status()"

# Default command (web API)
# Entrypoint runs migrations then starts uvicorn
CMD ["./docker-entrypoint.sh"]
