#!/bin/bash

# Start Uvicorn in the background
# We bind to 127.0.0.1 because Nginx is in the same container and will proxy to it
# We use port 8000 for the backend
echo "Starting Uvicorn..."
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning &
PID_UVICORN=$!

# Wait for Uvicorn to start
echo "Waiting for Uvicorn to start..."
while ! curl -s http://127.0.0.1:8000/healthz > /dev/null; do
  sleep 1
done
echo "Uvicorn started."

# Start Nginx in the foreground
# This keeps the container running
echo "Starting Nginx..."
nginx -g "daemon off;"