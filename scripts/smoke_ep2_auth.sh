#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="smoke-$(date +%s)@example.com"
PASSWORD="password12345"

echo "==> EP2 auth smoke: подготовка"
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

echo "==> EP2 auth smoke: runserver"
python manage.py runserver 127.0.0.1:8765 >/tmp/jira_import_smoke_ep2.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

echo "==> register"
REGISTER_CODE="$(curl -s -o /tmp/ep2_register.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/auth/register/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"password_confirm\":\"${PASSWORD}\"}")"
echo "Register HTTP: ${REGISTER_CODE}"
cat /tmp/ep2_register.json
if [ "$REGISTER_CODE" != "201" ]; then
  echo "ERROR: register failed"
  exit 1
fi

echo "==> fetch verification token from Mailhog"
sleep 1
MAIL_BODY="$(curl -sf "${MAILHOG_URL}/api/v2/messages" | python3 -c "
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
")"

echo "==> verify-email"
VERIFY_CODE="$(curl -s -o /tmp/ep2_verify.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/auth/verify-email/" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"${MAIL_BODY}\"}")"
echo "Verify HTTP: ${VERIFY_CODE}"
cat /tmp/ep2_verify.json
if [ "$VERIFY_CODE" != "200" ]; then
  echo "ERROR: verify failed"
  exit 1
fi

echo "==> login"
LOGIN_CODE="$(curl -s -o /tmp/ep2_login.json -w "%{http_code}" \
  -X POST "${BASE_URL}/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")"
echo "Login HTTP: ${LOGIN_CODE}"
cat /tmp/ep2_login.json
if [ "$LOGIN_CODE" != "200" ]; then
  echo "ERROR: login failed"
  exit 1
fi

ACCESS="$(python3 -c "import json; print(json.load(open('/tmp/ep2_login.json'))['access'])")"

echo "==> GET /api/me/"
ME_CODE="$(curl -s -o /tmp/ep2_me.json -w "%{http_code}" \
  -H "Authorization: Bearer ${ACCESS}" \
  "${BASE_URL}/api/me/")"
echo "Me HTTP: ${ME_CODE}"
cat /tmp/ep2_me.json
if [ "$ME_CODE" != "200" ]; then
  echo "ERROR: /api/me/ failed"
  exit 1
fi

echo "==> EP2 auth smoke: OK"
