#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p /root/crypto-trading-bot/logs

# Check if .env file exists
if [ ! -f /root/crypto-trading-bot/.env ]; then
    echo "Creating .env file..."
    cat > /root/crypto-trading-bot/.env << EOL
# Exchange API Keys
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
USE_TESTNET=True

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/crypto_trading
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_ECHO=False

# Trading Configuration
TRADING_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
TIMEFRAME=1m
UPDATE_INTERVAL=1.0

# Risk Management
MAX_POSITION_SIZE=0.1
MAX_LEVERAGE=3.0
RISK_PER_TRADE=0.02
MAX_OPEN_TRADES=5
MAX_CORRELATION=0.7
MIN_RISK_REWARD=2.0
MAX_DAILY_LOSS=0.05
MAX_DRAWDOWN=0.15

# Strategy Parameters
MACD_FAST_PERIOD=12
MACD_SLOW_PERIOD=26
MACD_SIGNAL_PERIOD=9
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30
BB_STD_DEV=2.0

# Market Data
INDICATOR_WINDOWS=20,50,200
ORDERBOOK_DEPTH=10

# Proxy Configuration
PROXY_HOST=your_proxy_host
PROXY_PORT=your_proxy_port
PROXY_USER=your_proxy_user
PROXY_PASS=your_proxy_pass
PROXY_LIST=port1,port2,port3
FAILOVER_PORTS=port1,port2,port3,port4
EOL
    echo "Please edit /root/crypto-trading-bot/.env with your actual configuration values"
fi

# Copy service file
cp scripts/crypto-trading-bot.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and start service
systemctl enable crypto-trading-bot.service
systemctl restart crypto-trading-bot.service

# Check status
echo "Checking service status..."
systemctl status crypto-trading-bot.service

echo "Setup complete. Please check the logs at /root/crypto-trading-bot/logs/trading_bot.log" 