#!/bin/bash

# Bulletproof deployment script for crypto trading bot
set -e

echo "🚀 Starting bulletproof deployment..."

# --------------------------
# 🔧 Configuration
# --------------------------
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"
VENV_DIR="$PROJECT_ROOT/venv"
SERVICES=("crypto-trading-api" "crypto-trading-bot" "crypto-trading-frontend")

# --------------------------
# 🧠 Helper functions
# --------------------------
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

kill_port() {
  local port=$1
  echo "🔪 Killing processes on port $port..."
  
  # Kill by port
  sudo lsof -ti:$port | sudo xargs kill -9 2>/dev/null || true
  
  # For port 3000, also kill react-scripts and node processes
  if [ "$port" = "3000" ]; then
    sudo pkill -f "react-scripts" 2>/dev/null || true
    sudo pkill -f "node.*3000" 2>/dev/null || true
    sudo pkill -f "webpack-dev-server" 2>/dev/null || true
    # Kill by process name patterns
    sudo fuser -k 3000/tcp 2>/dev/null || true
  fi
  
  sleep 3
  
  # Verify port is free
  if nc -z localhost "$port" 2>/dev/null; then
    echo "⚠️ Port $port still in use, trying harder..."
    sudo kill -9 $(sudo lsof -t -i:$port) 2>/dev/null || true
    sleep 2
  fi
}

fix_python_imports() {
  echo "🔧 Ensuring Python environment consistency..."
  
  # Don't change any code - make the VPS environment work like local
  # The issue is import resolution, not the code structure
  
  # Ensure proper Python path in systemd services
  export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
  
  # Create __init__.py files if missing to help Python recognize packages
  find "$PROJECT_ROOT/src" -type d -exec touch {}/__init__.py \; 2>/dev/null || true
  
  echo "✅ Python environment configured to match local"
}

# --------------------------
# 🛑 Stop all existing services
# --------------------------
echo "🛑 Stopping existing services..."
for service in "${SERVICES[@]}"; do
  if systemctl is-active --quiet "$service" 2>/dev/null; then
    echo "⏹️ Stopping $service..."
    sudo systemctl stop "$service" 2>/dev/null || true
  fi
done

# Kill processes on known ports
kill_port 3000  # Frontend
kill_port 8000  # API
kill_port 5432  # PostgreSQL (will restart with Docker)

# --------------------------
# 🐳 Database setup (Docker)
# --------------------------
echo "🐳 Setting up PostgreSQL database..."

# Install Docker if needed
if ! command_exists docker; then
  echo "📦 Installing Docker..."
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  sudo usermod -aG docker $USER
  rm get-docker.sh
fi

# Install Docker Compose if needed
if ! command_exists docker-compose; then
  echo "📦 Installing Docker Compose..."
  sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi

# Stop any existing PostgreSQL containers
echo "🛑 Cleaning up existing PostgreSQL containers..."
docker stop postgres crypto_trading_db 2>/dev/null || true
docker rm postgres crypto_trading_db 2>/dev/null || true

# Start PostgreSQL with docker-compose
echo "🐘 Starting PostgreSQL container..."
cd "$PROJECT_ROOT"
docker-compose up -d postgres
sleep 5

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
  if docker exec crypto_trading_db pg_isready -U trader -d crypto_trading 2>/dev/null; then
    echo "✅ PostgreSQL is ready"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ PostgreSQL failed to start"
    exit 1
  fi
  sleep 1
done

# --------------------------
# 🐍 Python environment setup
# --------------------------
echo "🐍 Setting up Python environment..."

# Install Python dependencies
if ! command_exists python3; then
  echo "📦 Installing Python 3..."
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip
fi

# Create virtual environment
if [ -d "$VENV_DIR" ]; then
  echo "🗑️ Removing old virtual environment..."
  rm -rf "$VENV_DIR"
fi

echo "🆕 Creating new virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install Python packages
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/requirements.txt"

# --------------------------
# 🌐 Frontend setup
# --------------------------
echo "🌐 Setting up frontend..."

# Install Node.js if needed
if ! command_exists node; then
  echo "📦 Installing Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# Install frontend dependencies
cd "$FRONTEND_DIR"
if [ -d "node_modules" ]; then
  echo "🗑️ Removing old node_modules..."
  rm -rf node_modules package-lock.json
fi

echo "📦 Installing frontend dependencies..."
npm install

# --------------------------
# 🔧 Fix code issues
# --------------------------
cd "$PROJECT_ROOT"
fix_python_imports

# Create logs directory
mkdir -p "$LOG_DIR"

# --------------------------
# 🚀 Create systemd services
# --------------------------
echo "🚀 Creating systemd services..."

# Get current user and paths
CURRENT_USER=$(whoami)
PYTHON_PATH="$VENV_DIR/bin/python"
NODE_PATH=$(which node)

# API Service
sudo tee /etc/systemd/system/crypto-trading-api.service > /dev/null << EOF
[Unit]
Description=Crypto Trading Bot API
After=network.target postgresql.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$PYTHON_PATH -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Bot Service
sudo tee /etc/systemd/system/crypto-trading-bot.service > /dev/null << EOF
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_ROOT
Environment="PYTHONPATH=$PROJECT_ROOT"
EnvironmentFile=$PROJECT_ROOT/.env
ExecStart=$PYTHON_PATH $PROJECT_ROOT/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Frontend Service
sudo tee /etc/systemd/system/crypto-trading-frontend.service > /dev/null << EOF
[Unit]
Description=Crypto Trading Bot Frontend
After=network.target postgresql.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$FRONTEND_DIR
Environment=PORT=3000
ExecStart=$NODE_PATH $FRONTEND_DIR/node_modules/.bin/react-scripts start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# --------------------------
# 🏃 Start services
# --------------------------
echo "🏃 Starting services..."

sudo systemctl daemon-reload

for service in "${SERVICES[@]}"; do
  echo "🚀 Starting $service..."
  sudo systemctl enable "$service"
  sudo systemctl start "$service"
  sleep 2
done

# --------------------------
# ✅ Verification
# --------------------------
echo "🔍 Verifying deployment..."

sleep 10

for service in "${SERVICES[@]}"; do
  if systemctl is-active --quiet "$service"; then
    echo "✅ $service is running"
  else
    echo "❌ $service failed to start"
    echo "📋 Last 10 log entries for $service:"
    sudo journalctl -u "$service" --no-pager -n 10
  fi
done

# Check ports
echo "🔍 Checking ports..."
if nc -z localhost 3000; then
  echo "✅ Frontend is accessible on port 3000"
else
  echo "❌ Frontend is not accessible on port 3000"
fi

if nc -z localhost 8000; then
  echo "✅ API is accessible on port 8000"
else
  echo "❌ API is not accessible on port 8000"
fi

if nc -z localhost 5432; then
  echo "✅ Database is accessible on port 5432"
else
  echo "❌ Database is not accessible on port 5432"
fi

echo ""
echo "🎉 Deployment completed!"
echo "📊 Frontend: http://localhost:3000"
echo "🔌 API: http://localhost:8000"
echo "📋 Check service status: sudo systemctl status crypto-trading-api crypto-trading-bot crypto-trading-frontend" 