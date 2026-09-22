#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
#
# ACA_API_HOST        interface uvicorn binds. The default 0.0.0.0 is correct
#                     inside a container (Railway, `docker run`), where the
#                     published port decides exposure. On a host-level install
#                     (gx-10, deploy/gx10/aca-api.service) it is 127.0.0.1 and
#                     `tailscale serve` is the only way in; see docs/TAILNET.md.
# ACA_FORWARDED_ALLOW_IPS  peers whose X-Forwarded-* headers uvicorn trusts. The
#                     client IP it resolves keys the login rate limiter, so a
#                     directly reachable API must not trust every peer.
# PORT                listen port (Railway assigns it dynamically).
echo "Starting application..."
exec uvicorn src.api.app:app \
    --host "${ACA_API_HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="${ACA_FORWARDED_ALLOW_IPS:-*}"
