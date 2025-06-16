# Crypto Trading Bot

A sophisticated cryptocurrency trading bot with a modern web interface for monitoring and control. The bot automatically scans all available futures pairs on Binance, identifies high-probability trading opportunities, and executes trades with advanced risk management.

## Key Features

### Dynamic Symbol Discovery
- Automatically discovers and monitors all available futures pairs
- Real-time scanning of market data
- Intelligent opportunity scoring based on multiple factors
- No manual symbol configuration required

### Dynamic Strategy Configuration & Adaptation
- **Strategy Profiles:** Define multiple trading strategies (Conservative, Moderate, Aggressive) with distinct parameter sets
- **Real-time Adaptation:** Strategy parameters automatically adjust based on market volatility and trading performance
- **Profile Management:** Easily switch between, edit, and create new strategy profiles via the UI

### Advanced Technical Analysis
- Multiple technical indicators:
  - Trend: MACD, EMA
  - Momentum: RSI, Stochastic
  - Volatility: Bollinger Bands, ATR
  - Volume: OBV, VWAP
  - Support/Resistance levels

### Risk Management
- Fixed risk per trade ($50 by default)
- Dynamic position sizing based on confidence score
- Maximum leverage limits
- Correlation monitoring
- Drawdown protection
- Stop-loss and take-profit calculation

### Real-time Monitoring
- Live WebSocket updates with API key authentication
- Modern React-based dashboard
- Real-time opportunity display
- Performance metrics
- Position management

### Advanced Filtering
- Minimum market cap ($100M)
- Maximum spread (0.2%)
- Minimum liquidity ($500K)
- Volatility range (1-5%)
- Volume requirements
- Correlation limits

### Market Data
- Comprehensive market data fetching:
  - OHLCV data with customizable intervals
  - Real-time funding rates
  - 24-hour statistics
  - Order book depth analysis
  - Spread and liquidity calculations
  - Open interest tracking
  - Volatility analysis
  - Volume analysis
- Caching system for optimized performance
- Rate limiting and retry mechanisms
- Proxy support with automatic failover

## System Architecture

The system consists of three main components:

1. **Trading Bot (Internal Service)**
   - Manages trading logic and risk management
   - Operates on a VPS
   - Communicates with exchanges
   - Processes market data
   - Generates trading signals

2. **Web Interface (Backend API)**
   - FastAPI-based REST API
   - WebSocket server for real-time updates with API key authentication
   - Runs on port 8000
   - Handles frontend communication

3. **Frontend (React Dashboard)**
   - React-based interface
   - Runs on port 3000
   - Real-time updates via WebSocket
   - Modern, responsive design

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/crypto-trading-bot.git
   cd crypto-trading-bot
   ```

2. **Install Dependencies**
   ```bash
   # Backend
   pip install -r requirements.txt

   # Frontend
   cd frontend
   npm install
   ```

3. **Configure Environment**
Create a `.env` file in the root directory:
```env
# Exchange API Keys
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
USE_TESTNET=True

# Frontend/Backend Communication
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/crypto_trading
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_ECHO=False

# Risk Management
RISK_PER_TRADE=50.0
MAX_OPEN_TRADES=5
MAX_LEVERAGE=20.0
MIN_RISK_REWARD=2.0
MAX_DAILY_LOSS=0.05
MAX_DRAWDOWN=0.15

# Technical Analysis
MACD_FAST_PERIOD=12
MACD_SLOW_PERIOD=26
MACD_SIGNAL_PERIOD=9
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30
BB_STD_DEV=2.0

# Market Data
INDICATOR_WINDOWS=20,50,200
ORDERBOOK_DEPTH=10

# Dynamic Symbol Discovery
SYMBOL_DISCOVERY_MODE=dynamic
TRADING_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT

# Signal Filtering
MIN_CONFIDENCE=0.4

# Service Configuration
BOT_LOG_LEVEL=INFO
API_LOG_LEVEL=INFO
FRONTEND_LOG_LEVEL=INFO

# WebSocket Authentication
API_KEY=your_api_key_here
```

Create a `frontend/.env` file:
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_API_KEY=your_api_key_here
```

4. **Initialize Database**
The database tables are automatically created and initial strategies are populated when the backend API service (`src/main.py`) starts for the first time.

5. **Setup Services**
Create systemd service files:

```bash
# Create systemd service files
sudo nano /etc/systemd/system/crypto-trading-bot.service
sudo nano /etc/systemd/system/crypto-trading-api.service
sudo nano /etc/systemd/system/crypto-trading-frontend.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable crypto-trading-bot
sudo systemctl enable crypto-trading-api
sudo systemctl enable crypto-trading-frontend

sudo systemctl start crypto-trading-bot
sudo systemctl start crypto-trading-api
sudo systemctl start crypto-trading-frontend
```

## Project Structure

```
crypto-trading-bot/
├── src/                      # Core trading bot source code
│   ├── api/                  # FastAPI backend and WebSocket server
│   ├── market_data/          # Market data fetching and processing
│   ├── signals/              # Trading signal generation
│   ├── risk/                 # Risk management system
│   ├── database/             # Database models and operations
│   ├── utils/                # Helper functions and utility classes
│   ├── ml/                   # Machine learning components
│   ├── strategy/             # Trading strategy implementation
│   ├── strategies/           # Strategy profiles and configurations
│   ├── opportunity/          # Opportunity detection and scoring
│   ├── models/               # Data models and schemas
│   ├── trading/              # Trading execution and management
│   └── logs/                 # Application logs
├── frontend/                 # React-based web dashboard
│   └── src/
│       ├── components/       # Reusable React components
│       ├── pages/           # Main application pages
│       ├── contexts/        # React context providers
│       └── layouts/         # Page layout components
├── config/                   # Configuration files
├── docs/                     # Project documentation
├── tests/                    # Test suite
├── scripts/                  # Setup and utility scripts
├── logs/                     # Application logs
├── data/                     # Data storage
├── cache/                    # Cache directory
├── requirements.txt          # Python dependencies
├── run_bot.py               # Main bot entry point
├── debug.py                 # Development debugging tools
└── README.md                # Project documentation
```

## Monitoring and Logs

The application logs are stored in the `logs/` directory:
- `api.log`: Backend API and WebSocket server logs
- `bot.log`: Trading bot logs
- `frontend.log`: Frontend service logs

## Security

### API Key Security
- Never commit API keys to the repository
- Use environment variables for sensitive data
- Rotate API keys regularly
- Use IP restrictions on exchange accounts

### WebSocket Authentication
- All WebSocket connections require a valid API key
- API key is passed as a query parameter in the WebSocket URL
- Invalid or missing API keys result in connection rejection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Update documentation
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
