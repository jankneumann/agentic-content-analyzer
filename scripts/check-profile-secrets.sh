#!/bin/bash
# Check for hardcoded secrets in profile files.
# Returns 0 (success) if NO secrets found, 1 (failure) if secrets detected.
#
# Profiles are committed; secrets are not. Every credential in a profile must be a
# ${VAR} reference resolved from .secrets.yaml or the environment.

set -uo pipefail

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
