#!/bin/bash

# Error handling
set -e
trap 'echo "Error occurred. Exiting..."; exit 1' ERR

# Function to check if a process is running
check_process() {
    pgrep -f "$1" > /dev/null
    return $?
}

# Function to start backend if not running
start_backend() {
    if ! check_process "src/main.py" && ! check_process "src/api/main.py"; then
        echo "Starting backend services..."
        
        # Start trading bot
        python src/main.py &
        TRADING_BOT_PID=$!
        echo "Trading bot started with PID: $TRADING_BOT_PID"
        
        # Start web interface
        python src/api/main.py &
        WEB_API_PID=$!
        echo "Web interface started with PID: $WEB_API_PID"
        
        # Wait a moment to ensure services are up
        sleep 2
        
        # Verify services are running
        if ! check_process "src/main.py" || ! check_process "src/api/main.py"; then
            echo "Error: Backend services failed to start"
            exit 1
        fi
    else
        echo "Backend services are already running"
        TRADING_BOT_PID=$(pgrep -f "src/main.py" || echo "")
        WEB_API_PID=$(pgrep -f "src/api/main.py" || echo "")
    fi
}

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv || { echo "Failed to create virtual environment"; exit 1; }
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r requirements.txt || { echo "Failed to install backend dependencies"; exit 1; }

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend || { echo "Failed to change to frontend directory"; exit 1; }
npm install || { echo "Failed to install frontend dependencies"; exit 1; }

# Start the application
echo "Starting the application..."
echo "Trading Bot will run in the background"
echo "Web Interface will run on http://localhost:8000"
echo "Frontend will run on http://localhost:3000"

# Start backend services
cd ..
start_backend

# Start frontend
cd frontend
npm start &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID"

# Handle script termination
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$TRADING_BOT_PID" ]; then
        kill $TRADING_BOT_PID 2>/dev/null || true
    fi
    if [ ! -z "$WEB_API_PID" ]; then
        kill $WEB_API_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "Shutdown complete"
    exit 0
}

trap cleanup INT TERM

# Wait for all processes
wait 