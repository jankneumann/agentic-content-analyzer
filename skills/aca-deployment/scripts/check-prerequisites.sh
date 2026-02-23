#!/usr/bin/env bash
# check-prerequisites.sh — Verify all deployment CLIs are installed and authenticated
#
# Usage:
#   bash skills/aca-deployment/scripts/check-prerequisites.sh
#
# Exit codes:
#   0 — All CLIs available (or at least aca is available)
#   1 — Critical failure (aca CLI not working)

set -uo pipefail

PASS=0
WARN=0
FAIL=0

check() {
  local name="$1"
  local check_cmd="$2"
  local install_hint="$3"
  local auth_cmd="${4:-}"

  printf "%-12s " "$name"

  if ! command -v "$name" &>/dev/null; then
    echo "NOT INSTALLED — $install_hint"
    WARN=$((WARN + 1))
    return
  fi

  # Version check
  local version
  version=$($check_cmd 2>&1 | head -1) || true

  if [ -n "$auth_cmd" ]; then
    if eval "$auth_cmd" &>/dev/null; then
      echo "OK (authenticated) — $version"
      PASS=$((PASS + 1))
    else
      echo "INSTALLED but NOT AUTHENTICATED — Run: $auth_cmd"
      WARN=$((WARN + 1))
    fi
  else
    echo "OK — $version"
    PASS=$((PASS + 1))
  fi
}

echo "=== ACA Deployment Prerequisites ==="
echo ""
echo "Checking CLI availability and authentication..."
echo ""

# aca — always available (built into this repo)
printf "%-12s " "aca"
if python -m src.cli --help &>/dev/null; then
  echo "OK (built-in)"
  PASS=$((PASS + 1))
else
  echo "FAIL — Python environment not activated? Run: source .venv/bin/activate"
  FAIL=$((FAIL + 1))
fi

# railway — npm package
check "railway" "railway --version" "npm i -g @railway/cli" "railway whoami"

# neonctl — npm package
check "neonctl" "neonctl --version" "npm i -g neonctl" "neonctl me"

# aura — standalone binary
check "aura" "aura version" "https://github.com/neo4j/aura-cli/releases" ""

# psql — optional, used for connectivity checks
printf "%-12s " "psql"
if command -v psql &>/dev/null; then
  PSQL_VERSION=$(psql --version 2>&1 | head -1)
  echo "OK (optional) — $PSQL_VERSION"
else
  echo "NOT INSTALLED (optional) — brew install libpq"
fi

echo ""
echo "=== Profile Configuration ==="
echo ""
echo "PROFILE=${PROFILE:-<not set>}"

if [ -n "${PROFILE:-}" ]; then
  # Show providers from profile
  python -m src.cli profile show "$PROFILE" 2>/dev/null | grep -E 'provider|database:|neo4j:|storage:|observability:' | head -10 || echo "  (could not read profile)"
fi

echo ""
echo "=== Neon Configuration ==="
echo ""

if [ -n "${NEON_API_KEY:-}" ]; then
  echo "NEON_API_KEY: set (${#NEON_API_KEY} chars)"
else
  echo "NEON_API_KEY: NOT SET — Required for neon:* actions"
fi

if [ -n "${NEON_PROJECT_ID:-}" ]; then
  echo "NEON_PROJECT_ID: $NEON_PROJECT_ID"
else
  echo "NEON_PROJECT_ID: NOT SET — Required for neon:* actions"
fi

echo ""
echo "=== Summary ==="
echo ""
echo "  Pass: $PASS | Warnings: $WARN | Failures: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "CRITICAL: Core CLI (aca) is not working. Fix before proceeding."
  exit 1
fi

if [ "$WARN" -gt 0 ]; then
  echo "Some CLIs are missing or unauthenticated."
  echo "Actions for unavailable CLIs will be skipped gracefully."
fi

echo "Ready to use: /aca-deployment <action>"
