#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="snapshots-smoke-$(date +%s)@example.com"
PASSWORD="password12345"
TMP_DIR="/tmp/snapshots_smoke_$$"
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

poll_source_ready() {
  local source_id="$1"
  local label="$2"
  for _ in $(seq 1 30); do
    curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${source_id}/" \
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

echo "==> Source snapshots smoke"
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
  -d '{"name":"Snapshots Smoke WS"}' > "${TMP_DIR}/ws.json"
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/ws.json'))['id'])")"

echo "==> build sample csv"
python3 <<'PY' > "${TMP_DIR}/sample.csv"
print("Summary,Priority\nFix login,High\nAdd export,Medium")
PY

echo "==> upload csv"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/sample.csv;type=text/csv" \
  -F "name=Smoke Snapshot CSV" > "${TMP_DIR}/upload.json"
SOURCE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/upload.json'))['id'])")"

echo "==> poll parse status"
poll_source_ready "$SOURCE_ID" "CSV"

echo "==> assert active_snapshot"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/detail.json"
python3 -c "
import json
d = json.load(open('${TMP_DIR}/detail.json'))
assert d.get('active_snapshot') and d['active_snapshot'].get('id'), d
print('    active_snapshot', d['active_snapshot']['id'])
"

echo "==> refresh-runs"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/refresh-runs/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/runs.json"
python3 -c "
import json
runs = json.load(open('${TMP_DIR}/runs.json'))
assert len(runs) >= 1, runs
assert runs[0]['status'] in ('succeeded', 'truncated'), runs[0]
print('    runs >= 1 OK, status=', runs[0]['status'])
"

echo "==> snapshots list/detail"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/snapshots/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/snaps.json"
ACTIVE_ID="$(python3 -c "
import json
snaps = json.load(open('${TMP_DIR}/snaps.json'))
assert len(snaps) >= 1, snaps
assert 'data' not in snaps[0], snaps[0]
active = next(s for s in snaps if s.get('is_active'))
print(active['id'])
")"
echo "    active snapshot id=${ACTIVE_ID}"

curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/snapshots/${ACTIVE_ID}/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/snap_detail.json"
python3 -c "
import json
d = json.load(open('${TMP_DIR}/snap_detail.json'))
sheets = (d.get('data') or {}).get('sheets') or []
assert sheets and 'rows' in sheets[0], d
assert len(sheets[0]['rows']) >= 1, sheets[0]
print('    snapshot detail rows OK')
"

echo "==> reparse"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/reparse/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{}' > "${TMP_DIR}/reparse.json"
poll_source_ready "$SOURCE_ID" "reparse"

echo "==> snapshots after reparse + compare"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/snapshots/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/snaps2.json"
python3 -c "
import json
snaps = json.load(open('${TMP_DIR}/snaps2.json'))
assert len(snaps) >= 2, snaps
print('    snapshots count', len(snaps))
"

curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/snapshots/compare/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/compare.json"
python3 -c "
import json
c = json.load(open('${TMP_DIR}/compare.json'))
assert 'summary' in c, c
assert c.get('current_id') and c.get('previous_id'), c
print('    compare summary OK', 'delta_rows=', c['summary'].get('row_count_delta'))
"

curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/refresh-runs/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/runs2.json"
python3 -c "
import json
runs = json.load(open('${TMP_DIR}/runs2.json'))
assert len(runs) >= 2, runs
print('    refresh-runs after reparse', len(runs))
"

echo "==> source snapshots smoke passed"
