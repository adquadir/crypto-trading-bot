#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting setup..."

# --------------------------
# 🔍 Auto-detect environment
# --------------------------
detect_environment() {
  if [ "$(whoami)" = "root" ] && ! command -v sudo >/dev/null && [ -d "/workspace" ]; then
    echo "codex"
  else
    echo "local"
  fi
}

ENVIRONMENT=${ENVIRONMENT:-$(detect_environment)}
echo "🔧 Detected environment: $ENVIRONMENT"

# --------------------------
# 📁 Path setup
# --------------------------
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"
VENV_DIR="$PROJECT_ROOT/venv"
mkdir -p "$LOG_DIR"

# --------------------------
# 🧠 Helper functions
# --------------------------
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

port_in_use() {
  nc -z localhost "$1" >/dev/null 2>&1
}

wait_for_service() {
  local host=$1
  local port=$2
  local max_retries=$3
  local attempt=1
  echo "⏳ Waiting for $host:$port..."
  while ! nc -z "$host" "$port"; do
    if [ $attempt -ge $max_retries ]; then
      echo "❌ Timeout waiting for $host:$port"
      return 1
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  echo "✅ $host:$port is ready"
  return 0
}

check_backend() {
  curl -s "http://$VPS_IP:$VPS_PORT/docs" >/dev/null
}

stop_existing_processes() {
  echo "(ℹ️ skip: no background processes managed here)"
}

# --------------------------
# 🌍 VPS + service defaults
# --------------------------
VPS_IP=${VPS_IP:-"localhost"}
VPS_PORT=${VPS_PORT:-"8000"}

AUTO_START_BOT=${AUTO_START_BOT:-"true"}
AUTO_START_API=${AUTO_START_API:-"true"}
AUTO_START_FRONTEND=${AUTO_START_FRONTEND:-"true"}

# --------------------------
# 🐍 Python setup
# --------------------------
echo "📦 Creating virtualenv..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/requirements.txt"

# --------------------------
# 💻 Frontend setup
# --------------------------
echo "🌐 Installing frontend dependencies..."
npm install --prefix "$FRONTEND_DIR"

# --------------------------
# 🐘 PostgreSQL via Docker (only outside Codex)
# --------------------------
if [[ "$ENVIRONMENT" != "codex" ]]; then
  echo "🐳 Starting PostgreSQL container..."
  if ! docker ps | grep -q postgres; then
    if port_in_use 5432; then
      echo "❌ Port 5432 already in use"
      exit 1
    fi
    docker run -d \
      --name postgres \
      -e POSTGRES_USER=trader \
      -e POSTGRES_PASSWORD=pass \
      -e POSTGRES_DB=crypto_trading \
      -p 5432:5432 \
      postgres:14
    wait_for_service localhost 5432 30 || exit 1
  else
    echo "ℹ️ PostgreSQL already running"
  fi
fi

# --------------------------
# 🚀 Service start functions
# --------------------------
start_api() {
  echo "🔌 Starting API (uvicorn)..."
  uvicorn src.main:app --host 0.0.0.0 --port 8000
}

start_frontend() {
  echo "🖥️ Starting frontend (React)..."
  npm start --prefix "$FRONTEND_DIR"
}

# --------------------------
# 🔁 Port checks
# --------------------------
for port in 8000 3000; do
  if port_in_use $port; then
    echo "❌ Port $port already in use"
    exit 1
  fi
done

# --------------------------
# 🧠 Environment-based behavior
# --------------------------
if [[ "$ENVIRONMENT" = "codex" ]]; then
  # Codex: foreground process
  start_api
else
  # Local/dev: background + logging
  start_api > "$LOG_DIR/api.log" 2>&1 &
  API_PID=$!
  start_frontend > "$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!

  echo "✅ Services launched:"
  echo "  API      → http://localhost:8000  (PID $API_PID)"
  echo "  Frontend → http://localhost:3000  (PID $FRONTEND_PID)"
  echo "📄 Logs saved to $LOG_DIR"

  wait_for_service localhost 8000 30
  wait_for_service localhost 3000 30

  trap 'kill $API_PID $FRONTEND_PID 2>/dev/null || true' EXIT
  wait
fi

echo "🎉 Setup completed successfully!"
