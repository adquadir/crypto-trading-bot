#!/bin/bash

# Error handling
set -e
trap 'echo "Error occurred. Exiting..."; exit 1' ERR

# Function to check if a process is running
check_process() {
    pgrep -f "$1" > /dev/null
    return $?
}

# Function to check if frontend is already running
check_frontend() {
    if check_process "node.*react-scripts start"; then
        echo "Frontend is already running"
        return 0
    fi
    return 1
}

# Function to stop existing frontend
stop_frontend() {
    echo "Stopping existing frontend..."
    pkill -f "node.*react-scripts start" || true
    sleep 2  # Give it time to shut down
}

# Function to check if backend is accessible
check_backend() {
    echo "Checking backend connection..."
    
    # Try to connect to the backend API
    if ! curl -s http://50.31.0.105:8000/api/trading/stats > /dev/null; then
        echo "Error: Cannot connect to backend API"
        echo "Please ensure your VPS backend is running and accessible"
        echo "You may need to set up port forwarding or update the API URL in the frontend"
        exit 1
    fi
    
    echo "Backend connection successful"
}

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv || { echo "Failed to create virtual environment"; exit 1; }
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend || { echo "Failed to change to frontend directory"; exit 1; }
npm install || { echo "Failed to install frontend dependencies"; exit 1; }

# Verify backend connection
check_backend

# Check if frontend is already running
if check_frontend; then
    read -p "Frontend is already running. Do you want to restart it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        stop_frontend
    else
        echo "Keeping existing frontend running"
        exit 0
    fi
fi

# Start the application
echo "Starting the application..."
echo "Backend is running on VPS (50.31.0.105:8000)"
echo "Frontend will run on http://localhost:3000"

# Start frontend
npm start &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID"

# Handle script termination
cleanup() {
    echo "Shutting down frontend..."
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "Shutdown complete"
    exit 0
}

trap cleanup INT TERM

# Wait for frontend process
wait 