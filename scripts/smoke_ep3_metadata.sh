#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MAILHOG_URL="${MAILHOG_URL:-http://127.0.0.1:8025}"
EMAIL="jira-meta-smoke-$(date +%s)@example.com"
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
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" > /tmp/jira_meta_smoke_login.json
}

echo "==> EP3 Jira metadata smoke"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis mailhog django celery 2>/dev/null || docker compose up -d db redis mailhog
  sleep 5
fi

register_verify_login
ACCESS="$(python3 -c 'import json; print(json.load(open("/tmp/jira_meta_smoke_login.json"))["access"])')"

echo "==> create workspace"
curl -sf -X POST "${BASE_URL}/api/workspaces/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Jira Metadata Smoke WS"}' >/tmp/jira_meta_smoke_ws.json
WORKSPACE_ID="$(python3 -c 'import json; print(json.load(open("/tmp/jira_meta_smoke_ws.json"))["id"])')"

JIRA_BASE_URL="${JIRA_BASE_URL:-https://example.atlassian.net}"
JIRA_EMAIL="${JIRA_EMAIL:-admin@example.com}"
JIRA_TOKEN="${JIRA_TOKEN:-dummy-token-for-smoke}"

echo "==> create jira connection"
curl -sf -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke Metadata Jira\",\"base_url\":\"${JIRA_BASE_URL}\",\"email\":\"${JIRA_EMAIL}\",\"api_token\":\"${JIRA_TOKEN}\",\"project_key\":\"PROJ\"}" \
  >/tmp/jira_meta_smoke_conn.json
CONN_ID="$(python3 -c 'import json; print(json.load(open("/tmp/jira_meta_smoke_conn.json"))["id"])')"

echo "==> get metadata pending"
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/${CONN_ID}/metadata/" \
  -H "Authorization: Bearer ${ACCESS}" >/tmp/jira_meta_smoke_get1.json

python3 <<'PY'
import json
data = json.load(open("/tmp/jira_meta_smoke_get1.json"))
assert "status" in data
assert "is_stale" in data
assert data["status"] in {"pending", "fresh", "syncing", "failed"}
print("initial status:", data["status"], "is_stale:", data["is_stale"])
PY

echo "==> start metadata sync"
HTTP_CODE="$(curl -s -o /tmp/jira_meta_smoke_sync.json -w '%{http_code}' -X POST \
  "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/${CONN_ID}/sync-metadata/" \
  -H "Authorization: Bearer ${ACCESS}")"

python3 <<PY
import json
code = "${HTTP_CODE}"
assert code == "202", f"expected 202, got {code}"
data = json.load(open("/tmp/jira_meta_smoke_sync.json"))
assert data["status"] == "syncing"
print("sync accepted:", data["detail"])
PY

echo "==> poll metadata after sync request"
sleep 2
curl -sf "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/jira-connections/${CONN_ID}/metadata/" \
  -H "Authorization: Bearer ${ACCESS}" >/tmp/jira_meta_smoke_get2.json

python3 <<PY
import json, os
data = json.load(open("/tmp/jira_meta_smoke_get2.json"))
assert "status" in data and "is_stale" in data
token = os.environ.get("JIRA_TOKEN", "")
if token and token != "dummy-token-for-smoke":
    if data["status"] == "fresh":
        assert isinstance(data.get("fields"), list)
        print("fresh metadata, fields:", len(data["fields"]))
    else:
        print("WARN: expected fresh with real JIRA_TOKEN, got", data["status"])
else:
    if data["status"] not in {"failed", "syncing"}:
        print("WARN: expected failed/syncing without real credentials, got", data["status"])
    print("post-sync status:", data["status"])
PY

echo "==> EP3 Jira metadata smoke: OK"
