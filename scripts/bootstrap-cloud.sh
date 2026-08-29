#!/usr/bin/env bash
# scripts/bootstrap-cloud.sh — One-time environment setup for cloud coding sessions
#
# Called by platform-specific hooks:
#   - Claude Code web: .claude/settings.json → hooks.SessionStart
#   - Codex: setup configuration
#
# Idempotent — safe to run multiple times. Skips steps that are already done.
# Writes status to stderr so stdout stays clean for hook context injection.
#
# Usage:
#   scripts/bootstrap-cloud.sh           # Full bootstrap
#   scripts/bootstrap-cloud.sh --check   # Dry-run: report what's missing

set -euo pipefail

# bootstrap_audit: durable pre-PostgreSQL terminal evidence (D6).
_BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_BOOTSTRAP_PROJECT_DIR="$(cd "$_BOOTSTRAP_SCRIPT_DIR/.." && pwd)"
bootstrap_audit_exit() {
    local command_status=$?
    trap - EXIT
    local outcome="succeeded"
    local diagnostic_code=""
    if [[ $command_status -ne 0 ]]; then
        outcome="permanent_failure"
        diagnostic_code="bootstrap.command_failed"
    fi
    local audit_status=0
    ACA_AUDIT_OUTCOME="$outcome" ACA_AUDIT_DIAGNOSTIC="$diagnostic_code" python3 - <<'PY' \
        >/dev/null || audit_status=$?
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path

directory = Path(os.environ.get("ACA_BOOTSTRAP_AUDIT_DIR", "/srv/aca/bootstrap-audit"))
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(str(directory), 0o700)
path = directory / "events.jsonl"
lock_path = directory / "events.lock"
lock_descriptor = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
try:
    os.fchmod(lock_descriptor, 0o600)
    fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
    previous_hash = None
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise RuntimeError("bootstrap audit permissions are not 0600")
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            claimed_hash = record.pop("record_hash")
            if record.get("previous_hash") != previous_hash:
                raise RuntimeError("bootstrap audit hash chain is corrupt")
            seed = bytes.fromhex(previous_hash) if previous_hash else b"aca-bootstrap-audit-v1"
            serialized = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            if hashlib.sha256(seed + serialized).hexdigest() != claimed_hash:
                raise RuntimeError("bootstrap audit record hash is corrupt")
            previous_hash = claimed_hash
    body = {
        "schema_version": 1,
        "occurred_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "entrypoint": "bootstrap.bootstrap_cloud",
        "outcome": os.environ["ACA_AUDIT_OUTCOME"],
        "diagnostic_code": os.environ.get("ACA_AUDIT_DIAGNOSTIC") or None,
        "metadata": {},
        "previous_hash": previous_hash,
    }
    seed = bytes.fromhex(previous_hash) if previous_hash else b"aca-bootstrap-audit-v1"
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["record_hash"] = hashlib.sha256(seed + serialized).hexdigest()
    descriptor = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
        os.write(descriptor, encoded.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
finally:
    os.close(lock_descriptor)
PY
    if [[ $command_status -eq 0 && $audit_status -ne 0 ]]; then
        command_status=$audit_status
    fi
    exit "$command_status"
}
trap bootstrap_audit_exit EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK_ONLY=false

if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
fi

# Track what needs attention
WARNINGS=()
INSTALLED=()
SKIPPED=()

log() { echo "[bootstrap] $*" >&2; }
warn() { WARNINGS+=("$*"); log "WARN: $*"; }
ok() { INSTALLED+=("$*"); log "OK: $*"; }
skip() { SKIPPED+=("$*"); log "SKIP: $*"; }

# ─────────────────────────────────────────────────────────────────────────────
# 1. Python — need 3.12+ (pyproject.toml requires-python >= 3.12)
# ─────────────────────────────────────────────────────────────────────────────

setup_python() {
    local py_version
    py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)

    if [[ "$py_major" -ge 3 && "$py_minor" -ge 12 ]]; then
        skip "Python $py_version already >= 3.12"
        return
    fi

    log "Python $py_version < 3.12 — installing via uv..."
    if $CHECK_ONLY; then
        warn "Python $py_version < 3.12 — needs uv python install 3.12"
        return
    fi

    if command -v uv &>/dev/null; then
        uv python install 3.12
        ok "Python 3.12 installed via uv"
    else
        warn "Python < 3.12 and uv not available — install Python 3.12+ manually"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. Virtual environment + project installation
# ─────────────────────────────────────────────────────────────────────────────

setup_venv() {
    cd "$PROJECT_DIR"

    if [[ -f ".venv/bin/activate" ]]; then
        skip ".venv already exists"
        # Still ensure the project is installed (editable)
        if [[ -f ".venv/bin/aca" ]]; then
            skip "aca CLI already installed"
            return
        fi
    fi

    if $CHECK_ONLY; then
        [[ -f ".venv/bin/activate" ]] || warn ".venv does not exist"
        [[ -f ".venv/bin/aca" ]] || warn "aca CLI not installed"
        return
    fi

    if command -v uv &>/dev/null; then
        if [[ ! -f ".venv/bin/activate" ]]; then
            uv venv .venv --python 3.12 2>&1 >&2
            ok "Created .venv with Python 3.12"
        fi
        # Install project in editable mode with dev deps
        uv pip install --python .venv/bin/python -e ".[dev]" 2>&1 >&2
        ok "Installed project + dev deps into .venv"
    else
        warn "uv not available — run: python3.12 -m venv .venv && pip install -e '.[dev]'"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. OpenSpec CLI
# ─────────────────────────────────────────────────────────────────────────────

setup_openspec() {
    if command -v openspec &>/dev/null; then
        skip "openspec already installed ($(openspec --version 2>/dev/null || echo 'unknown version'))"
        return
    fi

    if $CHECK_ONLY; then
        warn "openspec CLI not installed"
        return
    fi

    if command -v npm &>/dev/null; then
        npm install -g openspec 2>&1 >&2
        ok "Installed openspec CLI via npm"
    else
        warn "npm not available — cannot install openspec"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 4. Frontend dependencies
# ─────────────────────────────────────────────────────────────────────────────

setup_frontend() {
    if [[ -d "$PROJECT_DIR/web/node_modules" ]]; then
        skip "web/node_modules already exists"
        return
    fi

    if $CHECK_ONLY; then
        warn "web/node_modules missing"
        return
    fi

    if command -v pnpm &>/dev/null; then
        (cd "$PROJECT_DIR/web" && pnpm install --frozen-lockfile 2>&1 >&2)
        ok "Installed frontend deps via pnpm"
    else
        warn "pnpm not available — cannot install frontend deps"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 5. Activate venv for the current session (Claude Code hook integration)
# ─────────────────────────────────────────────────────────────────────────────

activate_venv() {
    # When called as a SessionStart hook, $CLAUDE_ENV_FILE lets us persist
    # environment variables across the session's Bash commands.
    if [[ -n "${CLAUDE_ENV_FILE:-}" && -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
        echo "source \"$PROJECT_DIR/.venv/bin/activate\"" >> "$CLAUDE_ENV_FILE"
        ok "Activated .venv via CLAUDE_ENV_FILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

log "Bootstrapping cloud environment..."
log "Project: $PROJECT_DIR"
log "Mode: $($CHECK_ONLY && echo 'check-only' || echo 'install')"

setup_python
setup_venv
setup_openspec
setup_frontend
activate_venv

# Summary
echo ""  >&2
log "──────────────────────────────────────"
log "Bootstrap complete."
[[ ${#INSTALLED[@]} -gt 0 ]] && log "  Installed: ${INSTALLED[*]}"
[[ ${#SKIPPED[@]} -gt 0 ]] && log "  Already OK: ${#SKIPPED[@]} items"
[[ ${#WARNINGS[@]} -gt 0 ]] && log "  Warnings: ${#WARNINGS[@]}" && for w in "${WARNINGS[@]}"; do log "    - $w"; done
log "──────────────────────────────────────"

# Exit 0 even with warnings — hooks should not block sessions
exit 0
