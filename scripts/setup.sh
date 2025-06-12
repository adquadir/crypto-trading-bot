#!/bin/bash

# Exit on error
set -e

echo "Starting setup..."

# VPS Configuration - configurable with defaults to localhost
VPS_IP=${VPS_IP:-"localhost"}
VPS_PORT=${VPS_PORT:-"8000"}

# Non-interactive configuration
AUTO_START_BOT=${AUTO_START_BOT:-"true"}
AUTO_START_API=${AUTO_START_API:-"true"}
AUTO_START_FRONTEND=${AUTO_START_FRONTEND:-"true"}
AUTO_INSTALL_DOCKER=${AUTO_INSTALL_DOCKER:-"true"}
AUTO_INSTALL_NODE=${AUTO_INSTALL_NODE:-"true"}

# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

# Function to install Docker
install_docker() {
    echo "Installing Docker..."
    DISTRO=$(detect_distro)
    
    case $DISTRO in
        "ubuntu"|"debian")
            # Update package list
            apt-get update -y

            # Install prerequisites
            apt-get install -y \
                apt-transport-https \
                ca-certificates \
                curl \
                gnupg \
                lsb-release

            # Add Docker's official GPG key
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

            # Set up the stable repository
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
                $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Update package list again
            apt-get update -y

            # Install Docker Engine
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        "centos"|"rhel"|"fedora")
            # Install prerequisites
            yum install -y yum-utils

            # Add Docker repository
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

            # Install Docker
            yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        *)
            echo "Unsupported distribution: $DISTRO"
            exit 1
            ;;
    esac

    # Start Docker service
    if command_exists systemctl; then
        systemctl start docker
        systemctl enable docker
    else
        service docker start
        chkconfig docker on
    fi

    # Add current user to docker group
    if ! groups $USER | grep -q docker; then
        usermod -aG docker $USER
        echo "Added $USER to docker group. You may need to log out and back in for this to take effect."
    fi

    echo "Docker installed successfully"
}

# Function to install Docker Compose
install_docker_compose() {
    echo "Installing Docker Compose..."
    DISTRO=$(detect_distro)
    
    case $DISTRO in
        "ubuntu"|"debian")
            # Install Docker Compose plugin
            apt-get install -y docker-compose-plugin
            ;;
        "centos"|"rhel"|"fedora")
            # Install Docker Compose plugin
            yum install -y docker-compose-plugin
            ;;
        *)
            echo "Unsupported distribution: $DISTRO"
            exit 1
            ;;
    esac

    # Create symlink for docker-compose command
    if [ -f /usr/libexec/docker/cli-plugins/docker-compose ]; then
        ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
    elif [ -f /usr/local/lib/docker/cli-plugins/docker-compose ]; then
        ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
    fi

    echo "Docker Compose installed successfully"
}

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
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        if [ "$AUTO_INSTALL_DOCKER" = "true" ]; then
            echo "Docker is not installed. Installing..."
            install_docker
        else
            echo "Error: Docker is not installed and AUTO_INSTALL_DOCKER is false"
            exit 1
        fi
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        if [ "$AUTO_INSTALL_DOCKER" = "true" ]; then
            echo "Docker Compose is not installed. Installing..."
            install_docker_compose
        else
            echo "Error: Docker Compose is not installed and AUTO_INSTALL_DOCKER is false"
            exit 1
        fi
    fi
    
    echo "All dependencies are satisfied"
}

# Function to setup database
setup_database() {
    echo "Setting up database..."
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        echo "Error: Docker is not running"
        exit 1
    fi
    
    # Start PostgreSQL container
    echo "Starting PostgreSQL container..."
    cd "$PROJECT_ROOT"
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U trader -d crypto_trading &> /dev/null; then
            break
        fi
        echo "Waiting for PostgreSQL to start... ($i/30)"
        sleep 1
    done
    
    if ! docker-compose exec -T postgres pg_isready -U trader -d crypto_trading &> /dev/null; then
        echo "Error: PostgreSQL failed to start"
        exit 1
    fi
    
    echo "Database setup completed"
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

# Main execution
echo "Starting setup..."

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

# Start services based on configuration
if [ "$AUTO_START_BOT" = "true" ]; then
    start_bot
fi

if [ "$AUTO_START_API" = "true" ]; then
    start_web_interface
fi

if [ "$AUTO_START_FRONTEND" = "true" ]; then
    start_frontend
fi

echo "Setup completed successfully!"

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