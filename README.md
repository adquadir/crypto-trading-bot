# Crypto Trading Bot

A sophisticated cryptocurrency trading bot with a modern web interface for monitoring and control. The bot automatically scans all available futures pairs on Binance, identifies high-probability trading opportunities, and executes trades with advanced risk management.

## Key Features

### Dynamic Symbol Discovery
- Automatically discovers and monitors all available futures pairs
- Real-time scanning of market data
- Intelligent opportunity scoring based on multiple factors
- No manual symbol configuration required

### Advanced Technical Analysis
- Multiple technical indicators:
  - Trend: MACD, EMA
  - Momentum: RSI, Stochastic
  - Volatility: Bollinger Bands, ATR
  - Volume: OBV, VWAP
  - Support/Resistance levels
- Sophisticated opportunity scoring:
  - Signal confidence (30%)
  - Technical indicators (25%)
  - Volume (15%)
  - Risk-reward ratio (15%)
  - Volatility (10%)
  - Leverage (5%)

### Risk Management
- Fixed risk per trade ($50 by default)
- Dynamic position sizing
- Maximum leverage limits
- Correlation monitoring
- Drawdown protection
- Stop-loss and take-profit calculation

### Real-time Monitoring
- Live WebSocket updates
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
   - WebSocket server for real-time updates
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
The bot supports two configuration methods:

A. **Environment Variables (Recommended)**
Create a `.env` file in the root directory:
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
```

B. **YAML Configuration (Alternative)**
Create configuration files in the `config/` directory:
- `config/default.yaml` - Default settings
- `config/production.yaml` - Production-specific settings

4. **Initialize Database**
```bash
python scripts/init_db.py
```

5. **Setup Services**
Choose one of the following methods:

A. **Quick Setup (Development)**
```bash
./scripts/setup.sh
```

B. **Service Setup (Production)**
```bash
sudo ./scripts/setup_service.sh
```

6. **Start the Services**
```bash
# Start the trading bot
python run_bot.py

# Start the web interface
cd frontend
npm start
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
│   ├── utils/                # Utility functions and helpers
│   └── ml/                   # Machine learning components
├── frontend/                 # React-based web dashboard
│   └── src/
│       ├── components/       # Reusable React components
│       └── pages/           # Main application pages
├── web/                      # Static web assets
├── docs/                     # Project documentation
├── config/                   # YAML configuration files
├── tests/                    # Test suite
├── scripts/                  # Setup and utility scripts
│   ├── setup.sh             # Development setup script
│   ├── setup_service.sh     # Production service setup
│   ├── crypto-trading-bot.service  # Systemd service file
│   └── init_db.py           # Database initialization
├── requirements.txt          # Python dependencies
├── run_bot.py               # Main bot entry point
├── debug.py                 # Development debugging tools
└── README.md                # Project documentation
```

### Directory Purposes

#### `src/`
- **api/**: Contains the FastAPI backend server and WebSocket implementation for real-time updates
- **market_data/**: Handles all exchange interactions, market data processing, and symbol discovery
- **signals/**: Implements technical analysis and trading signal generation
- **risk/**: Manages position sizing, risk limits, and portfolio management
- **database/**: Database models and operations for storing trade history and settings
- **utils/**: Common utility functions used across the project
- **ml/**: Machine learning components for advanced signal generation

#### `frontend/`
- **components/**: Reusable React components for the dashboard
- **pages/**: Main application pages and routing logic

#### `web/`
- Static web assets and legacy web interface (if any)

#### `docs/`
- API documentation
- Development guides
- Architecture documentation

#### `config/`
- YAML configuration files for different environments
- Default and production settings

#### `tests/`
- Unit tests
- Integration tests
- Test fixtures and utilities

#### `scripts/`
- **setup.sh**: Development environment setup script
- **setup_service.sh**: Production service installation script
- **crypto-trading-bot.service**: Systemd service configuration
- **init_db.py**: Database initialization and migration script

## API Endpoints

### REST Endpoints
- `GET /api/trading/opportunities` - Get top trading opportunities
- `GET /api/trading/opportunities/{symbol}` - Get detailed opportunity for a symbol
- `GET /api/trading/opportunities/stats` - Get opportunity statistics
- `GET /api/trading/signals` - Get trading signals
- `GET /api/trading/pnl` - Get profit and loss data
- `GET /api/trading/stats` - Get trading statistics
- `GET /api/trading/positions` - Get current positions
- `GET /api/trading/strategies` - Get strategy information
- `GET /api/trading/settings` - Get current settings

### WebSocket Endpoints
- `WS /ws/signals` - Real-time trading signals
- `WS /ws/opportunities` - Real-time opportunity updates

## Services

### Trading Bot Service
- Status: `