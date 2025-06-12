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
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
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

# --------------------------
# 🐍 Python setup
# --------------------------
echo "📦 Setting up Python environment..."

# Check for python3 and venv
if ! command_exists python3; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "❌ python3-venv is not installed"
    echo "Installing python3-venv..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# Create and activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "📦 Installing Python dependencies..."
pip install --upgrade pip

# Check if requirements.txt exists
if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found in $PROJECT_ROOT"
    exit 1
fi

pip install -r "$PROJECT_ROOT/requirements.txt"

# --------------------------
# 💻 Frontend setup
# --------------------------
echo "🌐 Installing frontend dependencies..."
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ Error: Frontend directory not found at $FRONTEND_DIR"
    exit 1
fi

cd "$FRONTEND_DIR"
npm install
cd "$PROJECT_ROOT"

# --------------------------
# 🐘 PostgreSQL setup
# --------------------------
if [[ "$ENVIRONMENT" != "codex" ]]; then
  echo "🐳 Checking PostgreSQL setup..."
  
  # Check if Docker is installed and running
  if ! command_exists docker; then
    echo "❌ Docker is not installed"
    echo "Installing Docker..."
    sudo apt-get update && sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "⚠️ Please log out and log back in for Docker group changes to take effect"
    exit 1
  fi

  # Check if user is in docker group
  if ! groups | grep -q docker; then
    echo "⚠️ Your user is not in the docker group"
    echo "Adding your user to the docker group..."
    sudo usermod -aG docker $USER
    echo "⚠️ Please log out and log back in for Docker group changes to take effect"
    exit 1
  fi

  # Check if PostgreSQL is already running
  if port_in_use 5432; then
    echo "ℹ️ PostgreSQL is already running on port 5432"
    echo "Checking if it's our Docker container..."
    if ! docker ps | grep -q postgres; then
      echo "⚠️ PostgreSQL is running but not in our Docker container"
      echo "Please stop the existing PostgreSQL service or use a different port"
      exit 1
    else
      echo "✅ Using existing PostgreSQL container"
    fi
  else
    echo "🐳 Starting PostgreSQL container..."
    docker run -d \
      --name postgres \
      -e POSTGRES_USER=trader \
      -e POSTGRES_PASSWORD=pass \
      -e POSTGRES_DB=crypto_trading \
      -p 5432:5432 \
      postgres:14
    wait_for_service localhost 5432 30 || exit 1
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

# If either service was started, ask about systemd setup
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Do you want to set up the services to start automatically with systemd? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Systemd setup not implemented in Docker mode"
    fi
fi

# Verify backend connection
if ! check_backend; then
    echo "Backend connection failed. Please check:"
    echo "1. Is the VPS running? ($VPS_IP)"
    echo "2. Is the backend service running? (sudo systemctl status crypto-trading-bot-web.service)"
    echo "3. Is port $VPS_PORT open? (sudo ufw status)"
    echo "4. Is the service listening on port $VPS_PORT? (sudo netstat -tulpn | grep $VPS_PORT)"
    exit 1
fi

# Start the application
echo "Starting the application..."
echo "Backend is running on http://$VPS_IP:$VPS_PORT"
echo "Frontend will run on http://localhost:3000"

# Handle script termination
cleanup() {
    echo "Shutting down services..."
    stop_existing_processes
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "Shutdown complete"
    exit 0
}

trap cleanup INT TERM

# Wait for frontend process
wait 