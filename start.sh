#!/bin/sh
# start.sh — Railway startup script
# Reads PORT from environment and starts Gunicorn
PORT="${PORT:-5000}"
echo "Starting Gunicorn on port $PORT"
exec gunicorn wsgi:app --bind "0.0.0.0:$PORT" --workers 1 --timeout 120
