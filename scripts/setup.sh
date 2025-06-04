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

# Function to check if bot is running
check_bot() {
    if check_process "src/main.py"; then
        echo "Trading bot is already running"
        return 0
    fi
    return 1
}

# Function to start the bot
start_bot() {
    echo "Starting trading bot..."
    cd ..  # Go back to project root
    python src/main.py > logs/trading_bot.log 2>&1 &
    BOT_PID=$!
    echo "Trading bot started with PID: $BOT_PID"
    cd frontend  # Return to frontend directory
}

# Function to create systemd service
create_systemd_service() {
    echo "Creating systemd service for trading bot..."
    
    # Create the service file
    sudo tee /etc/systemd/system/crypto-trading-bot.service << EOF
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=$(which python) src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable and start the service
    sudo systemctl enable crypto-trading-bot.service
    sudo systemctl start crypto-trading-bot.service
    
    echo "Systemd service created and started"
}

# Function to check if backend is accessible
check_backend() {
    echo "Checking backend connection..."
    echo "Testing connection to http://50.31.0.105:8000"
    
    # Try different connection methods
    echo "1. Testing basic connectivity..."
    if ! ping -c 1 50.31.0.105 > /dev/null 2>&1; then
        echo "Error: Cannot ping the server. Check if the IP is correct and the server is online."
        return 1
    fi
    
    echo "2. Testing port 8000..."
    if ! nc -z -w5 50.31.0.105 8000 > /dev/null 2>&1; then
        echo "Error: Port 8000 is not accessible. The service might not be running or the port might be blocked."
        return 1
    fi
    
    echo "3. Testing API endpoint..."
    if ! curl -s -m 5 http://50.31.0.105:8000/api/trading/stats > /dev/null; then
        echo "Error: API endpoint is not responding. The service might be running but not responding correctly."
        return 1
    fi
    
    echo "Backend connection successful"
    return 0
}

# Create logs directory if it doesn't exist
mkdir -p logs

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

# Check if bot is running
if ! check_bot; then
    read -p "Trading bot is not running. Do you want to start it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_bot
        
        # Ask about systemd setup
        read -p "Do you want to set up the bot to start automatically with systemd? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_systemd_service
        fi
    fi
fi

# Verify backend connection
if ! check_backend; then
    echo "Backend connection failed. Please check:"
    echo "1. Is the VPS running? (50.31.0.105)"
    echo "2. Is the backend service running? (sudo systemctl status crypto-trading-bot.service)"
    echo "3. Is port 8000 open? (sudo ufw status)"
    echo "4. Is the service listening on port 8000? (sudo netstat -tulpn | grep 8000)"
    exit 1
fi

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
    echo "Shutting down services..."
    if [ ! -z "$BOT_PID" ]; then
        kill $BOT_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "Shutdown complete"
    exit 0
}

trap cleanup INT TERM

# Wait for frontend process
wait 