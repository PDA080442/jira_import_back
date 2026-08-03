#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="sources-smoke-$(date +%s)@example.com"
PASSWORD="password12345"
TMP_DIR="/tmp/sources_smoke_$$"
mkdir -p "$TMP_DIR"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

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
    raise SystemExit('token not found in email')
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

echo "==> Sources files smoke"
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
  -d '{"name":"Sources Smoke WS"}' > "${TMP_DIR}/ws.json"
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/ws.json'))['id'])")"

echo "==> build sample files"
python3 <<'PY' > "${TMP_DIR}/sample.csv"
print("Summary,Priority\nFix login,High\nAdd export,Medium")
PY
python3 <<PY > "${TMP_DIR}/sample.xlsx"
import io
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "Backlog"
ws.append(["Summary", "Priority"])
ws.append(["Fix login", "High"])
buf = io.BytesIO()
wb.save(buf)
open("${TMP_DIR}/sample.xlsx", "wb").write(buf.getvalue())
PY

echo "==> upload csv"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/sample.csv;type=text/csv" \
  -F "name=Smoke CSV" > "${TMP_DIR}/csv_upload.json"
CSV_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/csv_upload.json'))['id'])")"

echo "==> upload xlsx"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/sample.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  -F "name=Smoke XLSX" > "${TMP_DIR}/xlsx_upload.json"
XLSX_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/xlsx_upload.json'))['id'])")"

poll_ready() {
  local id="$1"
  local label="$2"
  for i in $(seq 1 30); do
    curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${id}/" \
      -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/detail.json"
    STATUS="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/detail.json'))['status'])")"
    if [ "$STATUS" = "ready" ]; then
      echo "    ${label}: ready"
      return 0
    fi
    if [ "$STATUS" = "failed" ]; then
      python3 -c "import json; d=json.load(open('${TMP_DIR}/detail.json')); print(d.get('error_message',''))"
      return 1
    fi
    sleep 1
  done
  echo "    ${label}: timeout (still ${STATUS})"
  return 1
}

echo "==> poll parse status"
poll_ready "$CSV_ID" "CSV"
poll_ready "$XLSX_ID" "XLSX"

echo "==> list sources"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" | python3 -c "import json,sys; print('count', len(json.load(sys.stdin)))"

echo "==> negative: bad extension"
HTTP="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/sample.csv;filename=notes.txt;type=text/plain")"
test "$HTTP" = "400" && echo "    bad extension -> 400 OK"

echo "==> Sources smoke passed"
