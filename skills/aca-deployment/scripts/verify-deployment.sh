#!/usr/bin/env bash
# verify-deployment.sh — Cross-provider health check for the production stack
#
# Checks:
#   1. Railway API health (/health and /ready endpoints)
#   2. Neon database connectivity (via aca neon list)
#   3. AuraDB instance status (via aura CLI or profile fallback)
#   4. Active profile and provider configuration
#
# Usage:
#   bash skills/aca-deployment/scripts/verify-deployment.sh
#   API_URL=https://api.example.com bash skills/aca-deployment/scripts/verify-deployment.sh
#
# Environment:
#   API_URL — Override the API base URL (default: http://localhost:8000)
#
# Exit codes:
#   0 — All checks passed (or passed with warnings)
#   1 — Critical check failed

set -uo pipefail

API_URL="${API_URL:-http://localhost:8000}"
PASS=0
WARN=0
FAIL=0

section() {
  echo ""
  echo "=== $1 ==="
  echo ""
}

check_pass() {
  echo "  PASS: $1"
  PASS=$((PASS + 1))
}

check_warn() {
  echo "  WARN: $1"
  WARN=$((WARN + 1))
}

check_fail() {
  echo "  FAIL: $1"
  FAIL=$((FAIL + 1))
}

echo "ACA Stack Verification"
echo "======================"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo "API URL: $API_URL"

# ─────────────────────────────────────────────
# 1. Railway / API Health
# ─────────────────────────────────────────────
section "API Health"

# Liveness check
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  HEALTH_BODY=$(curl -s "$API_URL/health" 2>/dev/null)
  check_pass "/health — 200 OK ($HEALTH_BODY)"
else
  check_fail "/health — HTTP $HTTP_CODE (expected 200)"
  echo "         Is the API running? Check: curl $API_URL/health"
fi

# Readiness check
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/ready" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  READY_BODY=$(curl -s "$API_URL/ready" 2>/dev/null)
  check_pass "/ready — 200 OK"

  # Parse readiness checks from JSON
  if command -v python3 &>/dev/null; then
    echo "$READY_BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
checks = data.get('checks', {})
for k, v in checks.items():
    status = 'PASS' if v == 'ok' else 'WARN'
    print(f'         {status}: {k} = {v}')
" 2>/dev/null || true
  fi
elif [ "$HTTP_CODE" = "503" ]; then
  check_warn "/ready — 503 Service Unavailable (some dependencies degraded)"
  READY_BODY=$(curl -s "$API_URL/ready" 2>/dev/null)
  echo "         Response: $READY_BODY"
else
  check_fail "/ready — HTTP $HTTP_CODE (expected 200 or 503)"
fi

# Railway CLI status (optional)
if command -v railway &>/dev/null; then
  section "Railway Services"
  if railway whoami &>/dev/null; then
    railway status 2>/dev/null && check_pass "Railway project linked" || check_warn "Railway status unavailable"
  else
    check_warn "Railway CLI not authenticated — run: railway login"
  fi
else
  section "Railway Services"
  echo "  SKIP: railway CLI not installed"
fi

# ─────────────────────────────────────────────
# 2. Neon Database
# ─────────────────────────────────────────────
section "Neon Database"

if python -m src.cli neon list &>/dev/null; then
  BRANCH_COUNT=$(python -m src.cli neon list 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
  check_pass "Neon API reachable ($BRANCH_COUNT branches)"

  # Check for stale agent branches
  STALE_COUNT="$(python -m src.cli neon clean --dry-run 2>/dev/null | grep -c 'claude/' || true)"
  STALE_COUNT="${STALE_COUNT:-0}"
  if [ "$STALE_COUNT" -gt 0 ] 2>/dev/null; then
    check_warn "$STALE_COUNT stale agent branch(es) found — run: aca neon clean"
  fi
else
  # Check if it's a config issue vs connectivity issue
  if [ -z "${NEON_API_KEY:-}" ] || [ -z "${NEON_PROJECT_ID:-}" ]; then
    check_warn "Neon not configured (NEON_API_KEY or NEON_PROJECT_ID missing)"
    echo "         Set in .secrets.yaml or environment, or use PROFILE=railway-neon"
  else
    check_fail "Neon API unreachable — check NEON_API_KEY and NEON_PROJECT_ID"
  fi
fi

# ─────────────────────────────────────────────
# 3. AuraDB (Neo4j Knowledge Graph)
# ─────────────────────────────────────────────
section "AuraDB (Neo4j)"

if command -v aura &>/dev/null; then
  if aura instance list &>/dev/null; then
    # Check for running instances
    RUNNING=$(aura instance list 2>/dev/null | grep -ci "running" || echo "0")
    PAUSED=$(aura instance list 2>/dev/null | grep -ci "paused" || echo "0")

    if [ "$RUNNING" -gt 0 ]; then
      check_pass "AuraDB: $RUNNING instance(s) running"
    elif [ "$PAUSED" -gt 0 ]; then
      check_warn "AuraDB: $PAUSED instance(s) paused — resume with: aura instance resume <id>"
    else
      check_warn "AuraDB: No instances found"
    fi
  else
    check_warn "AuraDB CLI authentication failed — check credentials"
  fi
else
  echo "  SKIP: aura CLI not installed"
  # Fallback: check profile for Neo4j configuration
  if [ -n "${NEO4J_AURADB_URI:-}" ]; then
    echo "  INFO: NEO4J_AURADB_URI is configured (cannot verify connectivity without aura CLI)"
  elif [ -n "${NEO4J_URI:-}" ] || [ -n "${NEO4J_LOCAL_URI:-}" ]; then
    echo "  INFO: Local Neo4j configured (not AuraDB)"
  else
    check_warn "No Neo4j configuration detected"
  fi
fi

# ─────────────────────────────────────────────
# 4. Profile Configuration
# ─────────────────────────────────────────────
section "Profile"

echo "  PROFILE=${PROFILE:-<not set>}"
echo "  DATABASE_PROVIDER=${DATABASE_PROVIDER:-<from profile or default>}"
echo "  NEO4J_PROVIDER=${NEO4J_PROVIDER:-<from profile or default>}"
echo "  STORAGE_PROVIDER=${STORAGE_PROVIDER:-<from profile or default>}"
echo "  OBSERVABILITY_PROVIDER=${OBSERVABILITY_PROVIDER:-<from profile or default>}"

if [ -n "${PROFILE:-}" ]; then
  if python -m src.cli profile validate "$PROFILE" &>/dev/null; then
    check_pass "Profile '$PROFILE' is valid"
  else
    check_warn "Profile '$PROFILE' has validation warnings"
    python -m src.cli profile validate "$PROFILE" 2>&1 | head -10
  fi
fi

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
section "Summary"

echo "  Pass: $PASS | Warnings: $WARN | Failures: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL — $FAIL critical check(s) failed"
  echo ""
  echo "Troubleshooting:"
  echo "  Railway: See skills/aca-deployment/docs/railway-runbook.md"
  echo "  Neon:    See skills/aca-deployment/docs/neon-runbook.md"
  echo "  AuraDB:  See skills/aca-deployment/docs/auradb-runbook.md"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  echo "RESULT: PASS (with $WARN warning(s))"
else
  echo "RESULT: PASS — All checks passed"
fi
