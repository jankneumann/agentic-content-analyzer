#!/bin/bash
# Check for hardcoded secrets in profile files
# Returns 0 (success) if NO secrets found, 1 (failure) if secrets detected

if grep -rE "sk-ant-|sk-[a-zA-Z0-9]{20,}" profiles/*.yaml 2>/dev/null; then
    echo "ERROR: Hardcoded secrets detected in profile files!"
    echo "Use \${VAR} references instead of actual values."
    exit 1
fi

exit 0
