#!/usr/bin/env bash
# Operator step: store or rotate the third-party provider keys that
# render-secrets.sh hands to the API and worker, and re-upload the aca-gx10
# policy that grants the renderer read access to them.
#
# The provisioning ceremony writes policies once, so a policy edit after first
# install reaches OpenBao only through a step like this one.
#
# Values are read from the terminal, never argv: argv is world-readable in
# /proc and lands in shell history. jq takes them from its environment. A blank
# answer keeps the stored value and "-" removes it, so rotating one key never
# drops the others.
#
#   sudo /opt/aca/deploy/gx10/openbao/seed-providers-secret.sh
set -euo pipefail
umask 077
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
TOKEN_FILE="${GX10_BAO_TOKEN_FILE:-/etc/aca/gx10/bao-bootstrap-token}"
PROVIDERS_ENDPOINT="/secret/data/newsletter/gx10/providers"
POLICY_FILE="$(dirname "$0")/aca-gx10.hcl"
# Keep in step with PROVIDER_ENV in render-secrets.sh, which refuses any other field.
FIELDS=(gemini_api_key anthropic_api_key openai_api_key youtube_api_key tavily_api_key
  perplexity_api_key xai_api_key semantic_scholar_api_key elevenlabs_api_key
  voyage_api_key cohere_api_key jina_api_key)
[[ -s "$TOKEN_FILE" ]] || { echo "OpenBao admin token unavailable at $TOKEN_FILE" >&2; exit 1; }

work="$(mktemp -d)"; trap 'rm -rf -- "$work"' EXIT
printf 'header = "X-Vault-Token: %s"\n' "$(<"$TOKEN_FILE")" >"$work/curl"

# A missing path starts empty; any other failure stops here, because writing
# only the newly typed keys would silently drop every stored one.
status="$(curl -sS --config "$work/curl" -o "$work/current.json" -w '%{http_code}' "$BAO_ADDR$PROVIDERS_ENDPOINT")"
case "$status" in
  200) jq -e '.data.data | objects' "$work/current.json" >"$work/merged.json" ;;
  404) printf '{}\n' >"$work/merged.json" ;;
  *) echo "reading $PROVIDERS_ENDPOINT failed with HTTP $status" >&2; exit 1 ;;
esac

for field in "${FIELDS[@]}"; do
  stored="$(jq -r --arg f "$field" 'if has($f) then "stored" else "unset" end' "$work/merged.json")"
  read -rsp "$field [$stored; blank keeps, - removes] (hidden): " value; echo >&2
  [[ -n "$value" ]] || continue
  if [[ "$value" == - ]]; then
    jq --arg f "$field" 'del(.[$f])' "$work/merged.json" >"$work/next.json"
  else
    VALUE="$value" jq --arg f "$field" '.[$f] = env.VALUE' "$work/merged.json" >"$work/next.json"
  fi
  mv -f "$work/next.json" "$work/merged.json"
done

# The renderer refuses to start without an LLM key; refuse to store that state.
jq -e 'has("anthropic_api_key") or has("openai_api_key") or has("gemini_api_key")' "$work/merged.json" >/dev/null || {
  echo "refusing to store provider keys without anthropic_api_key, openai_api_key, or gemini_api_key" >&2; exit 1; }

jq '{data: .}' "$work/merged.json" >"$work/secret.json"
curl -fsS --config "$work/curl" -X POST --data-binary "@$work/secret.json" "$BAO_ADDR$PROVIDERS_ENDPOINT" >/dev/null
jq -n --rawfile policy "$POLICY_FILE" '{policy:$policy}' >"$work/policy.json"
curl -fsS --config "$work/curl" -X PUT --data-binary "@$work/policy.json" "$BAO_ADDR/sys/policies/acl/aca-gx10" >/dev/null
echo "stored $(jq -r 'keys | join(", ")' "$work/merged.json") and re-uploaded the aca-gx10 policy"
echo "apply with: systemctl restart aca-gx10-secrets.service aca-gx10.service"
