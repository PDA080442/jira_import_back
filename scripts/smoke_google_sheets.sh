#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="gsheets-smoke-$(date +%s)@example.com"
PASSWORD="password12345"
SAMPLE_ID="${GOOGLE_SHEETS_SMOKE_ID:-1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms}"
TMP_DIR="/tmp/gsheets_smoke_$$"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

extract_token_from_mailhog() {
  curl -sf "${MAILHOG_URL}/api/v2/messages" | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
items = data.get('items', [])
if not items:
    raise SystemExit('no mailhog messages')
body = items[0]['Content']['Body']
match = re.search(r'token=([A-Za-z0-9_-]+)', body)
if not match:
    raise SystemExit('token not found')
print(match.group(1))
"
}

register_verify_login() {
  curl -s -X POST "${BASE_URL}/api/auth/register/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"password_confirm\":\"${PASSWORD}\"}" >/dev/null
  sleep 1
  local verify_token
  verify_token="$(extract_token_from_mailhog)"
  curl -s -X POST "${BASE_URL}/api/auth/verify-email/" \
    -H "Content-Type: application/json" \
    -d "{\"token\":\"${verify_token}\"}" >/dev/null
  curl -s -X POST "${BASE_URL}/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" > "${TMP_DIR}/login.json"
}

echo "==> Google Sheets smoke"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis mailhog django celery 2>/dev/null || true
  sleep 5
fi

register_verify_login
ACCESS="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/login.json'))['access'])")"

echo "==> create workspace"
curl -sf -X POST "${BASE_URL}/api/workspaces/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Google Sheets Smoke WS"}' > "${TMP_DIR}/ws.json"
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/ws.json'))['id'])")"

echo "==> connect google sheet source"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/google-sheet-sources/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"spreadsheet_url\":\"https://docs.google.com/spreadsheets/d/${SAMPLE_ID}/edit\",\"name\":\"Smoke Sheet\"}" \
  > "${TMP_DIR}/create.json"
SOURCE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/create.json'))['id'])")"

poll_status() {
  for i in $(seq 1 30); do
    curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/google-sheet-sources/${SOURCE_ID}/" \
      -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/detail.json"
    STATUS="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/detail.json'))['status'])")"
    if [ "$STATUS" = "ready" ]; then
      echo "    snapshot: ready"
      python3 -c "import json; d=json.load(open('${TMP_DIR}/detail.json')); print('    tabs', len(d.get('tabs',[])))"
      return 0
    fi
    if [ "$STATUS" = "failed" ]; then
      ERROR="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/detail.json')).get('error_message',''))")"
      echo "    snapshot: failed — ${ERROR}"
      if echo "$ERROR" | grep -qi "not configured"; then
        echo "    (expected when GOOGLE_SERVICE_ACCOUNT_* is not set)"
        return 0
      fi
      return 1
    fi
    sleep 1
  done
  echo "    snapshot: timeout (still ${STATUS})"
  return 1
}

echo "==> poll snapshot"
poll_status

echo "==> negative: invalid url"
HTTP="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/google-sheet-sources/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"spreadsheet_url":"bad-url"}')"
test "$HTTP" = "400" && echo "    invalid url -> 400 OK"

echo "==> Google Sheets smoke passed"
