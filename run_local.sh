#!/bin/bash
set -e
cd "$(dirname "$0")"

# Kill any existing uvicorn
pkill -f "uvicorn" 2>/dev/null || true
sleep 1

echo "Starting ML service on :8001..."
ML_PID=$(.venv/bin/uvicorn ml_service.app:app --host 0.0.0.0 --port 8001 &>/tmp/ml_service.log & echo $!)

echo "Starting blockchain on :8002..."
BC_PID=$(.venv/bin/uvicorn blockchain.app:app --host 0.0.0.0 --port 8002 &>/tmp/blockchain.log & echo $!)

sleep 2

echo "Starting game server on :8000 (no Redis, in-memory)..."
GAME_PID=$(ML_SERVICE_URL=http://127.0.0.1:8001 \
  BLOCKCHAIN_SERVICE_URL=http://127.0.0.1:8002 \
  REDIS_URL="" \
  GAME_TIME_LIMIT_SECONDS=30 \
  ROOM_EXPIRY_SECONDS=15 \
  .venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000 &>/tmp/game_server.log & echo $!)

sleep 2

echo "=== ML service ==="
tail -3 /tmp/ml_service.log
echo "=== Blockchain ==="
tail -3 /tmp/blockchain.log
echo "=== Game server ==="
tail -5 /tmp/game_server.log

echo ""
echo "PIDs: ml=$ML_PID blockchain=$BC_PID game=$GAME_PID"
echo "Open http://localhost:8000 in your browser"
