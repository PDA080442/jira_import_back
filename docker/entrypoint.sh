#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for PostgreSQL..."
until python - <<'PY'
import os
import sys

import psycopg

url = os.environ.get("DATABASE_URL", "")
if not url:
    sys.exit(1)
try:
    conn = psycopg.connect(url, connect_timeout=3)
    conn.close()
except Exception:
    sys.exit(1)
PY
do
  sleep 1
done
echo "PostgreSQL is ready."

if [[ "${RUN_MIGRATIONS:-true}" == "true" ]]; then
  python manage.py migrate --noinput
fi

exec "$@"
