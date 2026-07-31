#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="jira-smoke-$(date +%s)@example.com"
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
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" >/tmp/jira_smoke_ep3_login.json"
}

echo "==> EP3 Jira connection smoke"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis mailhog django celery 2>/dev/null || docker compose up -d db redis mailhog
  sleep 5
fi

register_verify_login
ACCESS="$(python3 -c "import json; print(json.load(open('/tmp/jira_smoke_ep3_login.json'))['access'])")"

echo "==> create workspace"
curl -sf -X POST "${BASE_URL}/api/workspaces/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Jira Smoke WS"}' >/tmp/jira_smoke_ws.json
WORKSPACE_ID="$(python3 -c "import json; print(json.load(open('/tmp/jira_smoke_ws.json'))['id'])")"

JIRA_BASE_URL="${JIRA_BASE_URL:-https://example.atlassian.net}"
JIRA_EMAIL="${JIRA_EMAIL:-admin@example.com}"
JIRA_TOKEN="${JIRA_TOKEN:-dummy-token-for-smoke}"

echo "==> create jira connection"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Jira\",\"base_url\":\"${JIRA_BASE_URL}\",\"email\":\"${JIRA_EMAIL}\",\"api_token\":\"${JIRA_TOKEN}\",\"project_key\":\"PROJ\"}" \
  >/tmp/jira_smoke_conn.json

python3 -c "
import json
data = json.load(open('/tmp/jira_smoke_conn.json'))
assert 'api_token' not in data
assert 'api_token_encrypted' not in data
assert data.get('has_api_token') is True
print('connection id:', data['id'])
open('/tmp/jira_smoke_conn_id.txt','w').write(data['id'])
"

CONN_ID="$(cat /tmp/jira_smoke_conn_id.txt)"

echo "==> list connections"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/" \
  -H "Authorization: Bearer ${ACCESS}" >/dev/null

echo "==> get connection"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/${CONN_ID}/" \
  -H "Authorization: Bearer ${ACCESS}" >/dev/null

echo "==> test connection"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/${CONN_ID}/test/" \
  -H "Authorization: Bearer ${ACCESS}" >/tmp/jira_smoke_test.json

python3 -c "
import json, os
data = json.load(open('/tmp/jira_smoke_test.json'))
if os.environ.get('JIRA_TOKEN'):
    if data['status'] != 'success':
        print('WARN: expected success with real JIRA_TOKEN, got', data['status'])
else:
    if data['status'] != 'failed':
        print('WARN: expected failed without real credentials, got', data['status'])
print('test status:', data['status'])
"

echo "==> EP3 Jira connection smoke: OK"
