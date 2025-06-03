# Crypto Trading Bot

A sophisticated cryptocurrency trading bot that implements various technical analysis strategies with risk management and proxy support.

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
- Comprehensive API integration

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

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

## Configuration

The bot's configuration is managed through environment variables and the `config.py` file. Key configuration sections include:

### Exchange Configuration
- API keys for Binance
- Testnet mode for safe testing
- Trading symbols and timeframe

### Risk Management
- Maximum position size
- Leverage limits
- Risk per trade
- Maximum open trades
- Correlation limits
- Risk-reward ratio
- Daily loss limits
- Maximum drawdown

### Strategy Parameters
- MACD settings
- RSI thresholds
- Bollinger Bands parameters

### Market Data
- Indicator window sizes
- Orderbook depth
- Update intervals

### Proxy Configuration
- Proxy host and port
- Authentication credentials
- Proxy list for rotation
- Failover ports
- Health check settings

## Usage

1. Start the trading bot:
```bash
python run_bot.py
```

2. For debug mode:
```bash
python debug.py
```

3. Monitor the logs in `trading_bot.log`

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
│   │   └── endpoints.py
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