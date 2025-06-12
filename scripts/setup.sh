#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Codex setup..."

# --------------------------
# 📁 Path setup
# --------------------------
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)  # Go up one level to project root
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/logs"
VENV_DIR="$PROJECT_ROOT/venv"

# Create logs directory
mkdir -p "$LOG_DIR"

# --------------------------
# 🐍 Python setup
# --------------------------
echo "📦 Setting up Python environment..."

# Ensure python3 and venv are available
if ! command -v python3 >/dev/null; then
  echo "❌ python3 not found"
  exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "❌ python3-venv is not installed"
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
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
# 🚀 Start API (foreground process for Codex)
# --------------------------
echo "🔌 Starting API server..."
uvicorn src.main:app --host 0.0.0.0 --port 8000
