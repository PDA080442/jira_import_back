#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
OWNER_EMAIL="ws-owner-$(date +%s)@example.com"
INVITEE_EMAIL="ws-invitee-$(date +%s)@example.com"
PASSWORD="password12345"

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
  local email="$1"
  local token_file="$2"
  local access_file="$3"

  curl -s -X POST "${BASE_URL}/api/auth/register/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"${PASSWORD}\",\"password_confirm\":\"${PASSWORD}\"}" >/dev/null

  sleep 1
  local verify_token
  verify_token="$(extract_token_from_mailhog)"

  curl -s -X POST "${BASE_URL}/api/auth/verify-email/" \
    -H "Content-Type: application/json" \
    -d "{\"token\":\"${verify_token}\"}" >/dev/null

  curl -s -X POST "${BASE_URL}/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"${PASSWORD}\"}" >"${access_file}"

  echo "${verify_token}" > "${token_file}"
}

echo "==> EP2 workspace smoke: подготовка"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis mailhog
  sleep 3
fi

export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate --noinput

echo "==> EP2 workspace smoke: runserver"
python manage.py runserver 127.0.0.1:8765 >/tmp/jira_import_smoke_workspace.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

echo "==> owner register/verify/login"
register_verify_login "${OWNER_EMAIL}" /tmp/ws_owner_verify.txt /tmp/ws_owner_login.json
OWNER_ACCESS="$(python3 -c "import json; print(json.load(open('/tmp/ws_owner_login.json'))['access'])")"

echo "==> create workspace"
CREATE_CODE="$(curl -s -o /tmp/ws_create.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/workspaces/" \
  -H "Authorization: Bearer ${OWNER_ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Workspace"}')"
echo "Create HTTP: ${CREATE_CODE}"
cat /tmp/ws_create.json
if [ "$CREATE_CODE" != "201" ]; then
  echo "ERROR: create workspace failed"
  exit 1
fi

WS_ID="$(python3 -c "import json; print(json.load(open('/tmp/ws_create.json'))['id'])")"

echo "==> GET members (expect 1)"
MEMBERS_CODE="$(curl -s -o /tmp/ws_members.json -w "%{http_code}" \
  -H "Authorization: Bearer ${OWNER_ACCESS}" \
  "${BASE_URL}/api/workspaces/${WS_ID}/members/")"
echo "Members HTTP: ${MEMBERS_CODE}"
cat /tmp/ws_members.json
if [ "$MEMBERS_CODE" != "200" ]; then
  echo "ERROR: list members failed"
  exit 1
fi

echo "==> invite editor"
INVITE_CODE="$(curl -s -o /tmp/ws_invite.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/workspaces/${WS_ID}/invites/" \
  -H "Authorization: Bearer ${OWNER_ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${INVITEE_EMAIL}\",\"role\":\"editor\"}")"
echo "Invite HTTP: ${INVITE_CODE}"
cat /tmp/ws_invite.json
if [ "$INVITE_CODE" != "201" ]; then
  echo "ERROR: invite failed"
  exit 1
fi

echo "==> invitee register/verify/login"
register_verify_login "${INVITEE_EMAIL}" /tmp/ws_invitee_verify.txt /tmp/ws_invitee_login.json
INVITEE_ACCESS="$(python3 -c "import json; print(json.load(open('/tmp/ws_invitee_login.json'))['access'])")"

INVITE_TOKEN="$(extract_token_from_mailhog)"

echo "==> accept invite"
ACCEPT_CODE="$(curl -s -o /tmp/ws_accept.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/workspaces/invites/accept/" \
  -H "Authorization: Bearer ${INVITEE_ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"${INVITE_TOKEN}\"}")"
echo "Accept HTTP: ${ACCEPT_CODE}"
cat /tmp/ws_accept.json
if [ "$ACCEPT_CODE" != "200" ]; then
  echo "ERROR: accept invite failed"
  exit 1
fi

echo "==> GET members (expect 2)"
MEMBERS2="$(curl -s -H "Authorization: Bearer ${OWNER_ACCESS}" \
  "${BASE_URL}/api/workspaces/${WS_ID}/members/")"
MEMBER_COUNT="$(echo "$MEMBERS2" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['members']))")"
echo "Member count: ${MEMBER_COUNT}"
if [ "$MEMBER_COUNT" != "2" ]; then
  echo "ERROR: expected 2 members"
  exit 1
fi

echo "==> EP2 workspace smoke: OK"
