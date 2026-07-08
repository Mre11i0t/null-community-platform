#!/usr/bin/env bash
# Start the showcase in two detached `screen` sessions so it survives closing
# the terminal / SSH disconnects. Reattach later to view logs or restart.
#
#   ./scripts/showcase_screen.sh              # start (or restart) both
#   screen -ls                                # list the sessions
#   screen -r null-app                        # attach to gunicorn (Ctrl-A D to detach)
#   screen -r null-tunnel                     # attach to cloudflared
#   screen -S null-app -X quit                # stop the app
#   screen -S null-tunnel -X quit             # stop the tunnel
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "==> Ensuring db + redis are up"
docker compose up -d db redis >/dev/null

echo "==> Clearing any previous showcase processes/sessions"
screen -S null-app    -X quit 2>/dev/null || true
screen -S null-tunnel -X quit 2>/dev/null || true
pkill -f "gunicorn config.wsgi" 2>/dev/null || true
pkill -f "cloudflared tunnel run" 2>/dev/null || true
sleep 1

echo "==> Starting gunicorn in screen session 'null-app' (127.0.0.1:8000, localhost-only)"
screen -dmS null-app bash -lc "
  cd '$REPO'
  source venv/bin/activate
  set -a; source deploy/showcase/.env.showcase; set +a
  exec gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 \
       --access-logfile - --error-logfile -
"

echo "==> Starting cloudflared in screen session 'null-tunnel'"
screen -dmS null-tunnel bash -lc "exec cloudflared tunnel run null-showcase"

sleep 4
echo "==> Sessions:"
screen -ls | sed 's/^/    /' || true
echo "==> Local health:"
curl -s --retry 20 --retry-connrefused --retry-delay 1 -o /dev/null \
     -w "    app 127.0.0.1:8000 -> %{http_code}\n" -H "Host: bangalore.pavankarthick.in" http://127.0.0.1:8000/ || true
echo "Done. Public: https://bangalore.pavankarthick.in  |  Reattach: screen -r null-app"
