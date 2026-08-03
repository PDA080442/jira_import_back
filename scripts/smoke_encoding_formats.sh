#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="encoding-smoke-$(date +%s)@example.com"
PASSWORD="password12345"
TMP_DIR="/tmp/encoding_smoke_$$"
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

poll_until_ready() {
  local url="$1"
  local token="$2"
  for _ in $(seq 1 30); do
    curl -sf -H "Authorization: Bearer ${token}" "${url}" > "${TMP_DIR}/detail.json"
    status="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/detail.json'))['status'])")"
    if [[ "${status}" == "ready" ]]; then
      return 0
    fi
    if [[ "${status}" == "failed" ]]; then
      cat "${TMP_DIR}/detail.json"
      return 1
    fi
    sleep 1
  done
  echo "timeout waiting for ready"
  return 1
}

echo "==> Encoding formats smoke"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis mailhog django celery 2>/dev/null || true
  sleep 5
fi

register_verify_login
ACCESS="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/login.json'))['access'])")"

curl -sf -X POST "${BASE_URL}/api/workspaces/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Encoding Smoke WS"}' > "${TMP_DIR}/ws.json"
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/ws.json'))['id'])")"

python3 <<PY > "${TMP_DIR}/bom.csv"
raw = b"\\xef\\xbb\\xbfSummary;Priority\\nFix login;High\\n"
open("${TMP_DIR}/bom.csv", "wb").write(raw)
PY

echo "==> upload CSV with BOM and semicolon"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/bom.csv;type=text/csv" \
  -F "delimiter=semicolon" > "${TMP_DIR}/upload.json"
SOURCE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/upload.json'))['id'])")"
DETAIL_URL="${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/"

poll_until_ready "${DETAIL_URL}" "${ACCESS}"

python3 <<PY
import json
data = json.load(open("${TMP_DIR}/detail.json"))
assert data["status"] == "ready", data
assert data["delimiter"] == ";", data
codes = [w["code"] for w in data.get("warnings", [])]
assert "BOM_DETECTED" in codes, data
print("OK: BOM CSV parsed with delimiter=; and BOM_DETECTED warning")
PY

echo "==> reparse with delimiter=tab"
printf "A\tB\n1\t2\n" > "${TMP_DIR}/tab.csv"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/reparse/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"delimiter":"tab"}' >/dev/null

poll_until_ready "${DETAIL_URL}" "${ACCESS}"
python3 <<PY
import json
data = json.load(open("${TMP_DIR}/detail.json"))
assert data["delimiter_override"] == "\\t", data
print("OK: reparse stored tab delimiter override")
PY

echo "==> encoding formats smoke passed"
