#!/bin/bash

# Start Uvicorn in the background
# We bind to 127.0.0.1 because Nginx is in the same container and will proxy to it
# We use port 8000 for the backend
echo "Starting Uvicorn..."
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning &
PID_UVICORN=$!

# Wait for Uvicorn to start with a timeout (30 seconds)
echo "Waiting for Uvicorn to start..."
timeout=30
while ! curl -s http://127.0.0.1:8000/healthz > /dev/null; do
  if [ $timeout -le 0 ]; then
    echo "Uvicorn failed to start within 30 seconds or healthz not available."
    break
  fi
  sleep 1
  timeout=$((timeout-1))
done
echo "Proceeding to start Nginx..."

# Start Nginx in the foreground
# This keeps the container running
echo "Starting Nginx..."
nginx -g "daemon off;"