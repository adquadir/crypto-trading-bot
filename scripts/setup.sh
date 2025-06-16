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
# 🛠️ Systemd service management
# --------------------------
create_systemd_service() {
  local service_name=$1
  local description=$2
  local exec_start=$3
  local working_dir=$4
  local user=$5
  local environment=$6

  echo "📝 Creating systemd service: $service_name"
  
  # Create service file
  sudo tee "/etc/systemd/system/$service_name.service" > /dev/null << EOF
[Unit]
Description=$description
After=network.target postgresql.service

[Service]
Type=simple
User=$user
WorkingDirectory=$working_dir
Environment=$environment
ExecStart=$exec_start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  # Reload systemd and enable service
    sudo systemctl daemon-reload
  sudo systemctl enable "$service_name"
  sudo systemctl start "$service_name"
  
  echo "✅ Service $service_name created and started"
}

check_systemd_service() {
  local service_name=$1
  if systemctl is-active --quiet "$service_name"; then
    echo "✅ Service $service_name is running"
    return 0
  elif systemctl is-enabled --quiet "$service_name"; then
    echo "⚠️ Service $service_name exists but is not running"
    sudo systemctl start "$service_name"
    return 0
  else
    echo "❌ Service $service_name does not exist"
        return 1
    fi
}

setup_systemd_services() {
  local user=$(whoami)
  local python_path="$VENV_DIR/bin/python"
  local node_path=$(which node)
  
  # API Service
  if ! check_systemd_service "crypto-trading-api"; then
    create_systemd_service \
      "crypto-trading-api" \
      "Crypto Trading Bot API" \
      "$python_path -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000" \
      "$PROJECT_ROOT" \
      "$user" \
      "PYTHONPATH=$PROJECT_ROOT"
  fi
  
  # Bot Service
  if ! check_systemd_service "crypto-trading-bot"; then
    create_systemd_service \
      "crypto-trading-bot" \
      "Crypto Trading Bot" \
      "$python_path -m src.trading_bot" \
      "$PROJECT_ROOT" \
      "$user" \
      "PYTHONPATH=$PROJECT_ROOT"
  fi
  
  # Frontend Service
  if ! check_systemd_service "crypto-trading-frontend"; then
    create_systemd_service \
      "crypto-trading-frontend" \
      "Crypto Trading Bot Frontend" \
      "$node_path $FRONTEND_DIR/node_modules/.bin/react-scripts start" \
      "$FRONTEND_DIR" \
      "$user" \
      "PORT=3000"
  fi
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
# 🚀 Setup systemd services
# --------------------------
if [[ "$ENVIRONMENT" != "codex" ]]; then
  echo "🛠️ Setting up systemd services..."
  setup_systemd_services
fi

echo "🎉 Setup completed successfully!" 