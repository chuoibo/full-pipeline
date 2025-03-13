#!/bin/bash
set -e

# Kill any process using port 5000
echo "Checking if port 5000 is in use..."
if lsof -ti:5000 >/dev/null 2>&1; then
  echo "Port 5000 is in use. Killing the process..."
  kill -9 $(lsof -ti:5000) || echo "Failed to kill process"
  sleep 1
  echo "Process killed"
else
  echo "Port 5000 is available"
fi

# Start ASR module
echo "Starting ASR module..."
python ./backend/asr.py &

# Give it time to start
sleep 2

# Start API server
echo "Starting API server..."
echo "Host: $HOST, Port: $PORT"
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
uvicorn backend.app:app --host "$HOST" --port "$PORT"