#!/usr/bin/env bash
# One-shot showcase bootstrap — Mac Mini + Cloudflare Tunnel.
# See deploy/showcase/README.md. Run from the repo root with the venv active
# and the env loaded:
#   source venv/bin/activate
#   set -a; source deploy/showcase/.env.showcase; set +a
#   ./scripts/run_showcase.sh
set -euo pipefail

export DJANGO_SETTINGS_MODULE=config.settings.showcase

: "${ROOT_DOMAIN:?set ROOT_DOMAIN (e.g. null.example.com) — see deploy/showcase/.env.showcase}"
: "${DJANGO_SECRET_KEY:?set DJANGO_SECRET_KEY}"

echo "==> Starting MySQL + Redis (docker)"
docker compose up -d db redis

echo "==> Waiting for MySQL on ${MYSQL_SERVER:-127.0.0.1}:${MYSQL_PORT:-3307}"
for _ in $(seq 1 30); do
  if python - <<'PY' 2>/dev/null
import os, pymysql
pymysql.connect(
    host=os.environ.get("MYSQL_SERVER", "127.0.0.1"),
    port=int(os.environ.get("MYSQL_PORT", "3307")),
    user=os.environ.get("MYSQL_USERNAME", "root"),
    password=os.environ.get("MYSQL_PASSWORD", "s0m3p4ssw0rd"),
)
PY
  then echo "    MySQL is up"; break; fi
  sleep 2
done

echo "==> Migrating"
python manage.py migrate --noinput

echo "==> Collecting static"
python manage.py collectstatic --noinput

echo "==> Seeding demo data (idempotent)"
python manage.py shell < scripts/seed_rev3_data.py

echo "==> gunicorn on 127.0.0.1:8000  (Ctrl-C to stop; run the tunnel in another terminal)"
exec gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --access-logfile -
