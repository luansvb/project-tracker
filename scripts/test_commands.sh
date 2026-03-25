#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${API_BASE_URL:-}" ]]; then
  echo "Defina API_BASE_URL antes de executar."
  echo 'Exemplo: API_BASE_URL="https://abc123.execute-api.us-east-1.amazonaws.com" ./scripts/test_commands.sh'
  exit 1
fi

TRACKER_ID="${TRACKER_ID:-tracker-lt32-001}"

call_api() {
  local command="$1"

  echo ""
  echo ">>> ${command}"
  curl -s -X POST "${API_BASE_URL}/command" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  \"tracker_id\": \"${TRACKER_ID}\",
  \"command\": \"${command}\"
}
JSON
)"
  echo ""
}

echo ">>> Health"
curl -s "${API_BASE_URL}/health"
echo ""

call_api "STATUS#"
call_api "VERSION#"
call_api "PARAM#"
call_api "RELAY#"
call_api "RELAY,1#"
call_api "RELAY#"
call_api "RELAY,0#"
call_api "RELAY#"
