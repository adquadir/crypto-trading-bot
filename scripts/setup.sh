#!/bin/bash

# Error handling
set -e
trap 'echo "Error occurred. Exiting..."; exit 1' ERR

# VPS Configuration - configurable with defaults to localhost
VPS_IP=${VPS_IP:-"localhost"}
VPS_PORT=${VPS_PORT:-"8000"}

# Non-interactive configuration
AUTO_START_BOT=${AUTO_START_BOT:-"true"}
AUTO_START_API=${AUTO_START_API:-"true"}
AUTO_START_FRONTEND=${AUTO_START_FRONTEND:-"true"}
AUTO_INSTALL_POSTGRES=${AUTO_INSTALL_POSTGRES:-"true"}
AUTO_INSTALL_NODE=${AUTO_INSTALL_NODE:-"true"}

# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Function to check dependencies
check_dependencies() {
    echo "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        if [ "$AUTO_INSTALL_NODE" = "true" ]; then
            echo "Node.js is not installed. Installing..."
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -n bash -
            sudo -n apt-get install -y nodejs
        else
            echo "Error: Node.js is not installed and AUTO_INSTALL_NODE is false"
            exit 1
        fi
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        echo "Error: npm is not installed"
        exit 1
    fi
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        if [ "$AUTO_INSTALL_POSTGRES" = "true" ]; then
            echo "PostgreSQL is not installed. Installing..."
            sudo -n locale-gen en_US.UTF-8
            sudo -n update-locale LANG=en_US.UTF-8
            export LANG=en_US.UTF-8
            export LC_ALL=en_US.UTF-8
            
            sudo -n apt-get update
            sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib
        else
            echo "Error: PostgreSQL is not installed and AUTO_INSTALL_POSTGRES is false"
            exit 1
        fi
    fi
    
    echo "All dependencies are satisfied"
}

# Function to check if a port is available
check_port() {
    local port=$1
    if nc -z localhost $port > /dev/null 2>&1; then
        echo "Error: Port $port is already in use"
        return 1
    fi
    return 0
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local max_attempts=30
    local attempt=1
    
    echo "Waiting for service at $url..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null; then
            echo "Service is ready!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: Service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "Error: Service did not become ready in time"
    return 1
}

# Function to setup database
setup_database() {
    echo "Setting up database..."
    
    # Check if PostgreSQL is installed
    if ! command -v psql &> /dev/null; then
        if [ "$AUTO_INSTALL_POSTGRES" = "true" ]; then
            echo "PostgreSQL is not installed. Installing..."
            # Install locales package first
            sudo -n DEBIAN_FRONTEND=noninteractive apt-get update
            sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y locales
            
            # Configure locales non-interactively
            sudo -n /usr/sbin/locale-gen en_US.UTF-8
            sudo -n /usr/sbin/update-locale LANG=en_US.UTF-8
            export LANG=en_US.UTF-8
            export LC_ALL=en_US.UTF-8
            
            sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib
        else
            echo "Error: PostgreSQL is not installed and AUTO_INSTALL_POSTGRES is false"
            exit 1
        fi
    fi
    
    # Ensure PostgreSQL service is running
    if ! sudo -n systemctl is-active --quiet postgresql; then
        echo "Starting PostgreSQL service..."
        sudo -n systemctl start postgresql
        # Wait for PostgreSQL to be ready
        for i in {1..30}; do
            if sudo -n systemctl is-active --quiet postgresql; then
                break
            fi
            echo "Waiting for PostgreSQL to start... ($i/30)"
            sleep 1
        done
        
        if ! sudo -n systemctl is-active --quiet postgresql; then
            echo "Error: Failed to start PostgreSQL service"
            exit 1
        fi
    fi
    
    # Run database setup script
    echo "Running database setup script..."
    "$PROJECT_ROOT/scripts/setup_db.sh"
    
    echo "Database setup completed"
}

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

# Function to start the frontend
start_frontend() {
    echo "Starting frontend..."
    cd "$PROJECT_ROOT/frontend"  # Go to frontend directory
    npm install
    npm start > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend started with PID: $FRONTEND_PID"
    cd "$PROJECT_ROOT"  # Return to project root
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

# Check dependencies
check_dependencies

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Create virtual environment if it doesn't exist
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_ROOT/venv" || { echo "Failed to create virtual environment"; exit 1; }
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_ROOT/venv/bin/activate" || { echo "Failed to activate virtual environment"; exit 1; }

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt || { echo "Failed to install Python dependencies"; exit 1; }

# Setup database
setup_database

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd "$PROJECT_ROOT/frontend" || { echo "Failed to change to frontend directory"; exit 1; }
npm install || { echo "Failed to install frontend dependencies"; exit 1; }

# Stop any existing processes before starting new ones
stop_existing_processes
stop_frontend

# Check ports before starting services
if [ "$AUTO_START_API" = "true" ] && ! check_port $VPS_PORT; then
    echo "Error: Cannot start API service - port $VPS_PORT is in use"
    exit 1
fi

if [ "$AUTO_START_FRONTEND" = "true" ] && ! check_port 3000; then
    echo "Error: Cannot start frontend - port 3000 is in use"
    exit 1
fi

# Start services in order
if [ "$AUTO_START_BOT" = "true" ]; then
        start_bot
    sleep 2  # Give the bot time to initialize
fi

if [ "$AUTO_START_API" = "true" ]; then
        start_web_interface
    wait_for_service "http://$VPS_IP:$VPS_PORT/api/trading/stats"
    fi

if [ "$AUTO_START_FRONTEND" = "true" ]; then
    start_frontend
    wait_for_service "http://localhost:3000"
fi

echo "All services started successfully!"

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