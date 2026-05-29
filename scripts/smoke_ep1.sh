#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> EP1 smoke: подготовка окружения"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Создан .env из .env.example"
fi

pip install -q -r requirements.txt

echo "==> EP1 smoke: инфраструктура (PostgreSQL + Redis)"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis
  sleep 3
else
  echo "WARN: docker не найден — пропуск db/redis (readiness может вернуть 503)"
fi

echo "==> EP1 smoke: migrate + check"
python manage.py migrate --noinput
python manage.py check

echo "==> EP1 smoke: pytest"
pytest -q

echo "==> EP1 smoke: HTTP probes"
python manage.py runserver 127.0.0.1:8765 >/tmp/jira_import_smoke.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

curl -sf "http://127.0.0.1:8765/health/" | grep -q '"status":"ok"'
curl -sf -H "X-Trace-Id: smoke-trace" "http://127.0.0.1:8765/health/" -D /tmp/smoke_headers.txt -o /tmp/smoke_body.json
grep -qi "X-Trace-Id: smoke-trace" /tmp/smoke_headers.txt

READY_CODE="$(curl -s -o /tmp/ready.json -w "%{http_code}" "http://127.0.0.1:8765/ready/")"
echo "Readiness HTTP code: ${READY_CODE}"
cat /tmp/ready.json
if [ "$READY_CODE" != "200" ] && [ "$READY_CODE" != "503" ]; then
  echo "ERROR: unexpected readiness status code"
  exit 1
fi

echo "==> EP1 smoke: OK"
