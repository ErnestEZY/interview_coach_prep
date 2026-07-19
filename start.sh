#!/bin/bash
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PORT=${PORT:-8000}

# If Nginx is installed, we serve Uvicorn on 127.0.0.1:8000 and proxy through Nginx.
# Otherwise, bind Uvicorn directly to the Render-assigned PORT.
if [ -x "/usr/sbin/nginx" ]; then
  BACKEND_PORT=8000
  PROXY_MODE=yes
else
  BACKEND_PORT=${PORT}
  PROXY_MODE=no
fi

# Start Uvicorn in the background
echo "Starting Uvicorn on 127.0.0.1:${BACKEND_PORT}..."
uvicorn backend.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --log-level warning &
PID_UVICORN=$!

# Wait for Uvicorn to start with a timeout (30 seconds)
echo "Waiting for Uvicorn to start..."
timeout=30
while true; do
  if [ $timeout -le 0 ]; then
    echo "Uvicorn failed to start within 30 seconds or healthz not available."
    break
  fi
  if [ -x "/usr/bin/curl" ]; then
    /usr/bin/curl -s http://127.0.0.1:${BACKEND_PORT}/healthz > /dev/null && break
  else
    python - <<PY
import urllib.request
import sys
try:
    urllib.request.urlopen(f'http://127.0.0.1:{BACKEND_PORT}/healthz', timeout=1)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
    if [ $? -eq 0 ]; then
      break
    fi
  fi
  sleep 1
  timeout=$((timeout-1))
done

if [ "${PROXY_MODE}" = "yes" ]; then
  echo "Proceeding to start Nginx..."
  echo "Starting Nginx..."
  /usr/sbin/nginx -g "daemon off;"
else
  echo "Nginx not available, serving directly with Uvicorn on port ${PORT}."
  wait ${PID_UVICORN}
fi