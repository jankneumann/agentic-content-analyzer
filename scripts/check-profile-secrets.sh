#!/bin/bash
# Check for hardcoded secrets in profile files.
# Returns 0 (success) if NO secrets found, 1 (failure) if secrets detected.
#
# Profiles are committed; secrets are not. Every credential in a profile must be a
# ${VAR} reference resolved from .secrets.yaml or the environment.

set -uo pipefail

# bootstrap_audit: durable pre-PostgreSQL terminal evidence (D6).
_BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_BOOTSTRAP_PROJECT_DIR="$(cd "$_BOOTSTRAP_SCRIPT_DIR/.." && pwd)"
bootstrap_audit_exit() {
    local command_status=$?
    trap - EXIT
    local outcome="succeeded"
    local diagnostic_args=()
    if [[ $command_status -ne 0 ]]; then
        outcome="permanent_failure"
        diagnostic_args=(--diagnostic-code bootstrap.command_failed)
    fi
    local python_bin="python3"
    if [[ -x "$_BOOTSTRAP_PROJECT_DIR/.venv/bin/python" ]]; then
        python_bin="$_BOOTSTRAP_PROJECT_DIR/.venv/bin/python"
    fi
    local audit_status=0
    PYTHONPATH="$_BOOTSTRAP_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
        "$python_bin" -m src.clients.operational_observability \
        'bootstrap.check_profile_secrets' "$outcome" "${diagnostic_args[@]}" >/dev/null || audit_status=$?
    if [[ $command_status -eq 0 && $audit_status -ne 0 ]]; then
        command_status=$audit_status
    fi
    exit "$command_status"
}
trap bootstrap_audit_exit EXIT

fail() {
    echo "ERROR: Hardcoded secrets detected in profile files!"
    echo "Use \${VAR} references instead of actual values."
    exit 1
}

# LLM provider keys.
if grep -rE "sk-ant-|sk-[a-zA-Z0-9]{20,}" profiles/*.yaml 2>/dev/null; then
    fail
fi

# S3-shaped credentials for the backup target (and for the S3 storage provider).
#
# Matched on the VALUE, not just the key, so a `${BACKUP_S3_SECRET_ACCESS_KEY}`
# reference stays clean while a pasted literal does not. Two shapes:
#   - an AWS-style access key ID: AKIA/ASIA/AIDA/AROA + 16 base32 chars
#   - any *_secret_access_key / *_access_key_id / minio_root_password assigned a
#     bare literal rather than a ${...} reference
if grep -rEn "(AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}" profiles/*.yaml 2>/dev/null; then
    fail
fi

if grep -rEin "^[[:space:]]*[a-z0-9_]*(secret_access_key|access_key_id|root_password|age_identity)[[:space:]]*:[[:space:]]*[\"']?[^\$\"'[:space:]][^\"'[:space:]]*" \
    profiles/*.yaml 2>/dev/null; then
    fail
fi

exit 0
