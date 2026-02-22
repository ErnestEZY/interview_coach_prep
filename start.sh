#!/bin/bash

# Start Uvicorn in the background
# We bind to 127.0.0.1 because Nginx is in the same container and will proxy to it
# We use port 8000 for the backend
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# Start Nginx in the foreground
# This keeps the container running
nginx -g "daemon off;"