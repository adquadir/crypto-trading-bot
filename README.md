# Crypto Trading Bot

A sophisticated cryptocurrency trading bot with a modern web interface for monitoring and control.

## Architecture

The system consists of three main components:

1. **Trading Bot (Internal Service)**
   - Handles all trading logic and risk management
   - Runs internally on the VPS
   - Communicates with the exchange directly

2. **Web Interface (Backend API)**
   - FastAPI-based REST API and WebSocket server
   - Runs on port 8000
   - Provides endpoints for frontend communication
   - Available at `http://50.31.0.105:8000`

3. **Frontend (React Dashboard)**
   - Modern React-based web interface
   - Runs on port 3000
   - Real-time updates via WebSocket
   - Available at `http://localhost:3000`

## Features

- Real-time market data processing
- Multiple technical indicators (MACD, RSI, Bollinger Bands)
- Risk management system
- Position sizing and stop-loss calculation
- Database integration for trade history
- Configurable trading strategies
- Logging and monitoring
- Proxy support with failover
- Machine learning integration
- Debug mode for development
- Modern web dashboard
- Real-time trading signals
- Performance metrics and charts
- Position management
- Strategy configuration

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot
```

2. Run the setup script:
```bash
./scripts/setup.sh
```

This will:
- Create a virtual environment
- Install backend dependencies
- Install frontend dependencies
- Start the trading bot
- Start the web interface
- Start the frontend

3. Create a `.env` file in the root directory with the following variables:
```env
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
```

## Services

### Trading Bot Service
- Status: `sudo systemctl status crypto-trading-bot.service`
- Logs: `sudo journalctl -u crypto-trading-bot.service -f`
- Restart: `sudo systemctl restart crypto-trading-bot.service`

### Web Interface Service
- Status: `sudo systemctl status crypto-trading-bot-web.service`
- Logs: `sudo journalctl -u crypto-trading-bot-web.service -f`
- Restart: `sudo systemctl restart crypto-trading-bot-web.service`

### Frontend
- Status: `ps aux | grep "node.*react-scripts start"`
- Logs: `journalctl -f | grep "react-scripts"`

## API Endpoints

The web interface provides the following endpoints:

- `GET /` - API status and documentation
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation
- `GET /api/trading/signals` - Get trading signals
- `GET /api/trading/pnl` - Get profit and loss data
- `GET /api/trading/stats` - Get trading statistics
- `GET /api/trading/positions` - Get current positions
- `GET /api/trading/strategies` - Get strategy information
- `WS /ws/signals` - WebSocket for real-time signals

## Project Structure

```
crypto-trading-bot/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── trading_bot.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── exchange_client.py
│   │   └── processor.py
│   ├── signals/
│   │   ├── __init__.py
│   │   └── signal_engine.py
│   ├── risk/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── ml/
│   │   ├── __init__.py
│   │   └── predictor.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── manifest.json
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   ├── index.css
│   │   ├── components/
│   │   └── pages/
│   └── package.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_trading_bot.py
│   ├── test_exchange_client.py
│   ├── test_market_data.py
│   ├── test_signals.py
│   └── test_risk.py
├── scripts/
│   ├── setup.sh
│   └── deploy.sh
├── docs/
│   ├── api.md
│   └── development.md
├── config/
│   ├── default.yaml
│   └── production.yaml
├── requirements.txt
├── run_bot.py
├── debug.py
├── .env
└── README.md
```

## Testing

Run the test suite:
```bash
pytest tests/
```

For specific test files:
```bash
pytest tests/test_exchange_client.py -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This trading bot is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk and can result in the loss of your invested capital. You should not invest more than you can afford to lose. 