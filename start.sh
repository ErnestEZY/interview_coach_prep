#!/bin/bash
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PORT=${PORT:-10000}

# Detect nginx using PATH search — more portable than hardcoded /usr/sbin/nginx
NGINX_BIN=$(command -v nginx 2>/dev/null || echo "")

if [ -n "$NGINX_BIN" ]; then
  # Nginx is present: Uvicorn stays on loopback, Nginx proxies and faces the world
  BACKEND_HOST="127.0.0.1"
  BACKEND_PORT=8000
  PROXY_MODE=yes
  echo "Nginx found at: ${NGINX_BIN} — running in proxy mode"
else
  # No Nginx: Uvicorn must bind to 0.0.0.0 so Render's port scanner can reach it
  BACKEND_HOST="0.0.0.0"
  BACKEND_PORT="${PORT}"
  PROXY_MODE=no
  echo "Nginx not found — Uvicorn will serve directly on 0.0.0.0:${PORT}"
fi

# Start Uvicorn in the background
echo "Starting Uvicorn on ${BACKEND_HOST}:${BACKEND_PORT}..."
uvicorn backend.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --log-level warning &
PID_UVICORN=$!

# Wait up to 30 s for Uvicorn's /healthz to respond
echo "Waiting for Uvicorn to start..."
TIMEOUT=30
while true; do
  if [ "${TIMEOUT}" -le 0 ]; then
    echo "Uvicorn did not become healthy within 30 s; proceeding anyway."
    break
  fi
  if command -v curl > /dev/null 2>&1; then
    curl -sf "http://127.0.0.1:${BACKEND_PORT}/healthz" > /dev/null 2>&1 && break
  else
    python3 - <<PY
import urllib.request, sys
try:
    urllib.request.urlopen('http://127.0.0.1:${BACKEND_PORT}/healthz', timeout=1)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
    [ $? -eq 0 ] && break
  fi
  sleep 1
  TIMEOUT=$((TIMEOUT - 1))
done

if [ "${PROXY_MODE}" = "yes" ]; then
  echo "Starting Nginx in the foreground..."
  exec "${NGINX_BIN}" -g "daemon off;"
else
  echo "Serving directly via Uvicorn on port ${PORT}."
  wait "${PID_UVICORN}"
fi