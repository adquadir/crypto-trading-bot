#!/bin/bash

# Error handling
set -e
trap 'echo "Error occurred. Exiting..."; exit 1' ERR

# VPS Configuration
VPS_IP="50.31.0.105"
VPS_PORT="8000"

# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

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

# Function to check if web interface is running
check_web_interface() {
    if check_process "src/main.py"; then
        echo "API service is already running"
        return 0
    fi
    return 1
}

# Function to stop existing processes
stop_existing_processes() {
    echo "Stopping existing processes..."
    pkill -f "src/main.py" || true
    sleep 2  # Give them time to shut down
}

# Function to start the bot
start_bot() {
    echo "Starting trading bot..."
    cd "$PROJECT_ROOT"  # Go to project root
    python src/main.py > logs/trading_bot.log 2>&1 &
    BOT_PID=$!
    echo "Trading bot started with PID: $BOT_PID"
    cd frontend  # Return to frontend directory
}

# Function to start the web interface
start_web_interface() {
    echo "Starting API service..."
    cd "$PROJECT_ROOT"  # Go to project root
    python src/main.py > logs/web_interface.log 2>&1 &
    WEB_PID=$!
    echo "API service started with PID: $WEB_PID"
    cd frontend  # Return to frontend directory
}

# Function to create systemd service
create_systemd_service() {
    echo "Creating systemd service for trading bot..."
    
    # Create the trading bot service file
    sudo tee /etc/systemd/system/crypto-trading-bot.service << EOF
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Create the web interface service file
    sudo tee /etc/systemd/system/crypto-trading-bot-web.service << EOF
[Unit]
Description=Crypto Trading Bot Web Interface
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable and start the services
    sudo systemctl enable crypto-trading-bot.service
    sudo systemctl enable crypto-trading-bot-web.service
    sudo systemctl start crypto-trading-bot.service
    sudo systemctl start crypto-trading-bot-web.service
    
    echo "Systemd services created and started"
}

# Function to check if backend is accessible
check_backend() {
    echo "Checking backend connection..."
    echo "Testing connection to http://$VPS_IP:$VPS_PORT"
    
    # Try different connection methods
    echo "1. Testing basic connectivity..."
    if ! ping -c 1 $VPS_IP > /dev/null 2>&1; then
        echo "Error: Cannot ping the VPS. Check if the IP is correct and the server is online."
        return 1
    fi
    
    echo "2. Testing port $VPS_PORT..."
    if ! nc -z -w5 $VPS_IP $VPS_PORT > /dev/null 2>&1; then
        echo "Error: Port $VPS_PORT is not accessible. The service might not be running or the port might be blocked."
        return 1
    fi
    
    echo "3. Testing API endpoint..."
    if ! curl -s -m 5 http://$VPS_IP:$VPS_PORT/api/trading/stats > /dev/null; then
        echo "Error: API endpoint is not responding. The service might be running but not responding correctly."
        return 1
    fi
    
    echo "Backend connection successful"
    return 0
}

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Create virtual environment if it doesn't exist
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Creating virtual environment..."
    python -m venv "$PROJECT_ROOT/venv" || { echo "Failed to create virtual environment"; exit 1; }
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_ROOT/venv/bin/activate" || { echo "Failed to activate virtual environment"; exit 1; }

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd "$PROJECT_ROOT/frontend" || { echo "Failed to change to frontend directory"; exit 1; }
npm install || { echo "Failed to install frontend dependencies"; exit 1; }

# Stop any existing processes before starting new ones
stop_existing_processes

# Check if bot is running
if ! check_bot; then
    read -p "Trading bot is not running. Do you want to start it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_bot
    fi
fi

# Check if web interface is running
if ! check_web_interface; then
    read -p "API service is not running. Do you want to start it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_web_interface
    fi
fi

# If either service was started, ask about systemd setup
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Do you want to set up the services to start automatically with systemd? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_systemd_service
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
echo "Backend is running on http://$VPS_IP:$VPS_PORT"
echo "Frontend will run on http://localhost:3000"

# Start frontend
npm start &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID"

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