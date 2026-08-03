#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="presets-smoke-$(date +%s)@example.com"
PASSWORD="password12345"
TMP_DIR="/tmp/presets_smoke_$$"
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

echo "==> Source presets smoke"
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
  -d '{"name":"Presets Smoke WS"}' > "${TMP_DIR}/ws.json"
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/ws.json'))['id'])")"

echo "==> create file preset (comma)"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Comma CSV","source_type":"file","settings":{"delimiter":"comma","encoding":"utf-8"}}' \
  > "${TMP_DIR}/preset_v1.json"
PRESET_V1_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/preset_v1.json'))['id'])")"
PRESET_V1_VER="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/preset_v1.json'))['version'])")"
echo "    preset v1 id=${PRESET_V1_ID} version=${PRESET_V1_VER}"

echo "==> build semicolon csv sample"
python3 <<'PY' > "${TMP_DIR}/sample.csv"
print("Summary;Priority\nFix login;High\nAdd export;Medium")
PY

echo "==> upload csv with preset_id"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -F "file=@${TMP_DIR}/sample.csv;type=text/csv" \
  -F "name=Smoke Preset CSV" \
  -F "preset_id=${PRESET_V1_ID}" > "${TMP_DIR}/upload.json"
SOURCE_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/upload.json'))['id'])")"
python3 -c "
import json
d = json.load(open('${TMP_DIR}/upload.json'))
ap = d.get('applied_preset') or {}
assert ap.get('id') == '${PRESET_V1_ID}', d
print('    applied_preset OK')
"

echo "==> poll parse after upload"
poll_source_ready "$SOURCE_ID" "upload+ preset"

echo "==> create second preset (semicolon) for apply"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Semicolon CSV","source_type":"file","settings":{"delimiter":"semicolon","encoding":"utf-8"}}' \
  > "${TMP_DIR}/preset_apply.json"
PRESET_APPLY_ID="$(python3 -c "import json; print(json.load(open('${TMP_DIR}/preset_apply.json'))['id'])")"

echo "==> apply preset to existing source"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/apply-preset/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"preset_id\":\"${PRESET_APPLY_ID}\"}" > "${TMP_DIR}/binding.json"
python3 -c "
import json
b = json.load(open('${TMP_DIR}/binding.json'))
assert b.get('status') == 'applied', b
print('    binding status=applied OK')
"

echo "==> poll parse after apply"
poll_source_ready "$SOURCE_ID" "apply preset"

echo "==> verify delimiter override"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-files/${SOURCE_ID}/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/after_apply.json"
python3 -c "
import json
d = json.load(open('${TMP_DIR}/after_apply.json'))
assert d.get('delimiter_override') == ';', d
print('    delimiter_override=; OK')
"

echo "==> list recent configs"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/recent/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/recent.json"
python3 -c "
import json
items = json.load(open('${TMP_DIR}/recent.json'))
assert len(items) >= 1, items
print('    recent count', len(items))
"

echo "==> bump preset v1 version (patch settings)"
curl -sf -X PATCH "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/${PRESET_V1_ID}/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"settings":{"delimiter":"tab","encoding":"utf-8"}}' > "${TMP_DIR}/preset_v2.json"
python3 -c "
import json
d = json.load(open('${TMP_DIR}/preset_v2.json'))
assert d.get('version') == 2, d
print('    preset version bumped to 2 OK')
"

echo "==> check is_stale on recent binding for upload preset"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/recent/" \
  -H "Authorization: Bearer ${ACCESS}" > "${TMP_DIR}/recent_stale.json"
python3 -c "
import json
items = json.load(open('${TMP_DIR}/recent_stale.json'))
stale = [i for i in items if i.get('is_stale')]
assert stale, items
print('    is_stale=true present OK')
"

echo "==> list presets"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/source-presets/?source_type=file" \
  -H "Authorization: Bearer ${ACCESS}" | python3 -c "import json,sys; print('    preset count', len(json.load(sys.stdin)))"

echo "==> Source presets smoke passed"
