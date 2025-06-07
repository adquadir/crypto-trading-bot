# Crypto Trading Bot

A sophisticated cryptocurrency trading bot with a modern web interface for monitoring and control. The bot automatically scans all available futures pairs on Binance, identifies high-probability trading opportunities, and executes trades with advanced risk management.

## Key Features

### Dynamic Symbol Discovery
- Automatically discovers and monitors all available futures pairs
- Real-time scanning of market data
- Intelligent opportunity scoring based on multiple factors
- No manual symbol configuration required

### Dynamic Strategy Configuration & Adaptation
- **Strategy Profiles:** Define multiple trading strategies (Conservative, Moderate, Aggressive) with distinct parameter sets.
- **Real-time Adaptation:** Strategy parameters automatically adjust based on market volatility and trading performance (win rate, profit factor).
- **Profile Management:** Easily switch between, edit, and create new strategy profiles via the UI.

### Advanced Technical Analysis
- Multiple technical indicators:
  - Trend: MACD, EMA, **ADX, Ichimoku Cloud**
  - Momentum: RSI, Stochastic, **CCI**
  - Volatility: Bollinger Bands, ATR
  - Volume: OBV, VWAP
  - Support/Resistance levels
  - **Safe Candle-Based Opportunity Detection:**
    - Identifies hovering zones with tight price ranges
    - Detects small candle bodies indicating consolidation
    - Monitors decreasing volatility through ATR trend
    - Analyzes horizontal volume clusters
    - Calculates precise entry, take-profit, and stop-loss levels
    - Provides both long (SAFE_BUY) and short (SAFE_SELL) opportunities
    - Targets small, consistent profits ($25-$35 per trade)

### Risk Management
- Fixed risk per trade ($50 by default) - **now dynamically calculated per strategy profile**
- Dynamic position sizing - **adapted based on confidence score and strategy profile**
- Maximum leverage limits - **adapted based on confidence score and strategy profile**
- Correlation monitoring
- Drawdown protection - **configurable per strategy profile**
- Stop-loss and take-profit calculation - **based on dynamic parameters**

### Real-time Monitoring
- Live WebSocket updates
- Modern React-based dashboard
- Real-time opportunity display
- Performance metrics - **including profile-specific performance metrics**
- Position management
- **Parameter Adaptation History and Volatility Impact visualization**

### Advanced Filtering
- Minimum market cap ($100M)
- Maximum spread (0.2%)
- Minimum liquidity ($500K)
- Volatility range (1-5%)
- Volume requirements
- Correlation limits

### Market Data
- Comprehensive market data fetching through `get_market_data`:
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

# Frontend/Backend Communication
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 # Comma-separated list of allowed frontend origins (e.g., http://yourfrontend.com)

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
# SYMBOL_DISCOVERY_MODE: Set to 'dynamic' to automatically discover pairs, or 'static' to use TRADING_SYMBOLS.
# TRADING_SYMBOLS is ignored when SYMBOL_DISCOVERY_MODE is 'dynamic'.
SYMBOL_DISCOVERY_MODE=dynamic # or 'static'
TRADING_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT # Comma-separated list (only used if SYMBOL_DISCOVERY_MODE is 'static')
```

B. **YAML Configuration (Alternative)**
Create configuration files in the `config/` directory:
- `config/default.yaml` - Default settings
- `config/production.yaml` - Production-specific settings

4. **Initialize Database**
The database tables are automatically created and initial strategies are populated when the backend API service (`src/api/main.py`) starts for the first time. There is no separate `init_db.py` script to run.

   If you need to perform database migrations for schema changes, it is recommended to use a dedicated migration tool like Alembic.

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
│   ├── utils/                # Helper functions and utility classes, including configuration loading
│   ├── ml/                   # Machine learning components
│   └── strategy/             # Dynamic strategy configuration and profile management
├── frontend/                 # React-based web dashboard
│   └── src/
│       ├── components/       # Reusable React components
│       └── pages/           # Main application pages
├── web/                      # Static web assets
├── docs/                     # Project documentation
├── config/                   # YAML configuration files
├── tests/                    # Test suite, **including tests for the Candle Cluster Detector and safe-entry logic**
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
- **database/**: Database models and operations
- **utils/**: Helper functions and utility classes, **including configuration loading**
- **ml/**: Machine learning components
- **strategy/**: **Dynamic strategy configuration and profile management**

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
- **Includes specific tests for the `Candle Cluster Detector` and associated safe-entry logic.**

#### `scripts/`
- **setup.sh**: Development environment setup script
- **setup_service.sh**: Production service installation script
- **crypto-trading-bot.service**: Systemd service configuration
- **init_db.py**: Database initialization and migration script

## API Endpoints

### REST Endpoints
- `GET /api/trading/opportunities` - Get top trading opportunities based on current dynamic scan and filtering.
- `GET /api/trading/opportunities/{symbol}` - Get detailed opportunity information for a specific symbol.
- `GET /api/trading/opportunities/stats` - Get statistics about available trading opportunities (total, long/short counts, average confidence/score, top performers, including SAFE_BUY/SAFE_SELL signals).
- `GET /api/trading/signals` - Get recent trading signals (Note: Real-time signals are primarily via WebSocket).
- `GET /api/trading/pnl` - Get profit and loss data.
- `GET /api/trading/stats` - Get comprehensive trading statistics, **including profile-specific performance metrics, parameter adaptation history, and volatility impact.**
- `GET /api/trading/positions` - Get current open positions.
- `GET /api/trading/strategies` - Get list of available strategy profiles and their performance summaries.
- `GET /api/trading/settings` - Get current general bot settings.
- `PUT /api/trading/settings` - Update general bot settings.
- `PUT /api/trading/strategies/{profile_name}` - **Update parameters for a specific strategy profile.**
- `GET /api/market/data/{symbol}` - Get comprehensive market data for a symbol
- `GET /api/market/orderbook/{symbol}` - Get order book data
- `GET /api/market/funding/{symbol}` - Get current funding rate
- `GET /api/market/interest/{symbol}` - Get open interest
- `GET /api/market/historical/{symbol}` - Get historical OHLCV data

### WebSocket Endpoints
- `WS /ws/signals` - Real-time trading signals and market data updates.
- `WS /ws/opportunities` - Real-time updates on newly discovered trading opportunities.
- **WS /ws/stats** - **Real-time updates for dashboard statistics, including profile performance and parameter changes.**

## Services

### Trading Bot Service
- Status: `

## Testing

### Backend Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src tests/

# Run specific test file
pytest tests/test_market_data.py

# Run tests with detailed output
pytest -v
```

### Frontend Tests
```bash
# Run all tests
cd frontend
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in CI mode
npm run test:ci
```

### Test Coverage Requirements
- Minimum 80% code coverage
- All critical paths must be tested
- Integration tests for API endpoints
- End-to-end tests for critical user flows

## Monitoring and Logging

### Log Files
- Main log: `trading_bot.log`
- API log: `api.log`
- Error log: `error.log`

### Monitoring Dashboard
Access the monitoring dashboard at `http://localhost:3000/monitoring` to view:
- System health metrics
- Trading performance
- Error rates
- API response times
- WebSocket connection status

### Alerting
The system sends alerts for:
- Critical errors
- Risk limit breaches
- API failures
- System resource issues

### Page Availability Verification
The system includes automated health checks for all pages and API endpoints. Run the verification script to ensure all components are responding correctly:

```bash
# Run health checks
python scripts/verify_health.py

# Check specific component
python scripts/verify_health.py --component frontend
python scripts/verify_health.py --component api
python scripts/verify_health.py --component websocket
```

#### Health Check Checklist
1. **Frontend Pages**
   - Dashboard (`/`)
   - Opportunities (`/opportunities`)
   - Signals (`/signals`)
   - Positions (`/positions`)
   - Strategies (`/strategies`)
   - Settings (`/settings`)
   - Monitoring (`/monitoring`)

2. **API Endpoints**
   - Trading opportunities
   - Trading signals
   - PnL data
   - Trading statistics
   - Current positions
   - Strategy information
   - Settings

3. **WebSocket Connections**
   - Signal updates
   - Opportunity updates
   - Connection stability
   - Message delivery

4. **Database Connectivity**
   - Connection pool
   - Query performance
   - Transaction handling

#### Manual Verification Steps
1. **Frontend Health**
   ```bash
   # Check frontend build
   cd frontend
   npm run build
   
   # Verify static assets
   python scripts/verify_assets.py
   ```

2. **API Health**
   ```bash
   # Test API endpoints
   python scripts/test_endpoints.py
   
   # Check API response times
   python scripts/check_performance.py
   ```

3. **WebSocket Health**
   ```bash
   # Test WebSocket connections
   python scripts/test_websockets.py
   
   # Monitor WebSocket stability
   python scripts/monitor_websockets.py --duration 3600
   ```

4. **Database Health**
   ```bash
   # Check database connection
   python scripts/check_db.py
   
   # Verify database performance
   python scripts/benchmark_db.py
   ```

#### Automated Monitoring
The system includes automated monitoring that:
- Checks page availability every 5 minutes
- Verifies API response times
- Monitors WebSocket connection stability
- Tracks database performance
- Sends alerts for any failures

#### Health Check Dashboard
Access the health check dashboard at `http://localhost:3000/health` to view:
- Component status
- Response times
- Error rates
- Connection stability
- Resource usage

## Troubleshooting

### Common Issues

1. **API Connection Issues**
   ```bash
   # Check API connectivity
   python scripts/test_api.py
   
   # Verify API keys
   python scripts/verify_keys.py
   ```

2. **Database Connection**
   ```bash
   # Test database connection
   python scripts/test_db.py
   
   # Reset database (development only)
   python scripts/reset_db.py
   ```

3. **WebSocket Issues**
   - Check WebSocket connection status in the dashboard
   - Verify firewall settings
   - Check proxy configuration if using one

4. **Performance Issues**
   - Monitor system resources
   - Check log files for errors
   - Verify rate limits are not being exceeded

### Debug Mode
Enable debug mode for detailed logging:
```bash
# Set debug environment variable
export DEBUG=True

# Or modify .env file
DEBUG=True
```

## Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Update documentation
6. Submit a pull request

### Code Style
- Follow PEP 8 for Python code
- Use ESLint for JavaScript/TypeScript
- Write clear, descriptive commit messages
- Include docstrings for all functions

### Pull Request Process
1. Update the README.md with details of changes
2. Update the version numbers in relevant files
3. Ensure all tests pass
4. Request review from maintainers

## Security

### API Key Security
- Never commit API keys to the repository
- Use environment variables for sensitive data
- Rotate API keys regularly
- Use IP restrictions on exchange accounts

### System Security
- Keep all dependencies updated
- Use HTTPS for all communications
- Implement rate limiting
- Monitor for suspicious activity

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please:
1. Check the [documentation](docs/)
2. Search existing [issues](https://github.com/yourusername/crypto-trading-bot/issues)
3. Create a new issue if needed

## Acknowledgments

- [Binance API](https://binance-docs.github.io/apidocs/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
- [Material-UI](https://mui.com/)

## Deployment

### Docker Deployment
```bash
# Build the Docker image
docker build -t crypto-trading-bot .

# Run the container
docker run -d \
  --name crypto-trading-bot \
  -p 8000:8000 \
  -p 3000:3000 \
  --env-file .env \
  crypto-trading-bot
```

### Cloud Deployment

#### AWS Deployment
1. **EC2 Setup**
   ```bash
   # Launch EC2 instance
   aws ec2 run-instances \
     --image-id ami-0c55b159cbfafe1f0 \
     --instance-type t2.micro \
     --key-name your-key-pair \
     --security-group-ids sg-xxxxxxxx
   ```

2. **Load Balancer Configuration**
   ```bash
   # Create Application Load Balancer
   aws elbv2 create-load-balancer \
     --name crypto-trading-alb \
     --subnets subnet-xxxxxxxx subnet-yyyyyyyy \
     --security-groups sg-xxxxxxxx
   ```

3. **Auto Scaling Group**
   ```bash
   # Create launch configuration
   aws autoscaling create-launch-configuration \
     --launch-configuration-name crypto-trading-lc \
     --image-id ami-0c55b159cbfafe1f0 \
     --instance-type t2.micro
   ```

#### GCP Deployment
1. **Compute Engine Setup**
   ```bash
   # Create instance
   gcloud compute instances create crypto-trading-bot \
     --machine-type e2-medium \
     --zone us-central1-a \
     --image-family ubuntu-2004-lts
   ```

2. **Load Balancer Setup**
   ```bash
   # Create load balancer
   gcloud compute forwarding-rules create crypto-trading-lb \
     --target-pool crypto-trading-pool \
     --ports 80,443
   ```

### Scaling Considerations
- Use horizontal scaling for API servers
- Implement database sharding for large datasets
- Use Redis for caching and session management
- Implement rate limiting per instance
- Use CDN for static assets

## Performance Tuning

### Database Optimization
1. **Index Optimization**
   ```sql
   -- Add indexes for frequently queried columns
   CREATE INDEX idx_opportunities_symbol ON opportunities(symbol);
   CREATE INDEX idx_signals_timestamp ON signals(timestamp);
   ```

2. **Query Optimization**
   ```sql
   -- Use materialized views for complex queries
   CREATE MATERIALIZED VIEW mv_daily_stats AS
   SELECT date_trunc('day', timestamp) as day,
          COUNT(*) as total_trades,
          SUM(profit_loss) as total_pnl
   FROM trades
   GROUP BY day;
   ```

3. **Connection Pooling**
   ```python
   # Configure connection pool
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=10
   DB_POOL_TIMEOUT=30
   ```

### API Performance
1. **Response Caching**
   ```python
   # Enable response caching
   CACHE_TTL=300  # 5 minutes
   CACHE_TYPE="redis"
   ```

2. **Rate Limiting**
   ```python
   # Configure rate limits
   RATE_LIMIT_REQUESTS=100
   RATE_LIMIT_PERIOD=60  # seconds
   ```

3. **Compression**
   ```python
   # Enable response compression
   COMPRESS_LEVEL=6
   COMPRESS_MIN_SIZE=500
   ```

### WebSocket Optimization
1. **Connection Management**
   ```python
   # Configure WebSocket settings
   WS_MAX_CONNECTIONS=1000
   WS_PING_INTERVAL=30
   WS_PING_TIMEOUT=10
   ```

2. **Message Batching**
   ```python
   # Configure message batching
   BATCH_SIZE=50
   BATCH_INTERVAL=1  # seconds
   ```

## Backup and Recovery

### Database Backup
1. **Automated Backups**
   ```bash
   # Create backup script
   #!/bin/bash
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   pg_dump -U $DB_USER -d $DB_NAME > backup_$TIMESTAMP.sql
   ```

2. **Backup Schedule**
   ```bash
   # Add to crontab
   0 0 * * * /path/to/backup.sh  # Daily backup
   0 0 * * 0 /path/to/full_backup.sh  # Weekly full backup
   ```

### Configuration Backup
1. **Environment Backup**
   ```bash
   # Backup .env file
   cp .env .env.backup
   ```

2. **YAML Config Backup**
   ```bash
   # Backup config files
   tar -czf config_backup.tar.gz config/
   ```

### Disaster Recovery
1. **Database Recovery**
   ```bash
   # Restore from backup
   psql -U $DB_USER -d $DB_NAME < backup_file.sql
   ```

2. **Configuration Recovery**
   ```bash
   # Restore configuration
   cp .env.backup .env
   tar -xzf config_backup.tar.gz
   ```

## API Documentation

### Authentication
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

### Rate Limiting
- 100 requests per minute per IP
- 1000 requests per hour per API key
- Headers:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

### Error Codes
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Too Many Requests
- 500: Internal Server Error

### Example Requests

#### Get Trading Opportunities
```http
GET /api/trading/opportunities
Authorization: Bearer your_token_here

Response:
{
  "opportunities": [
    {
      "symbol": "BTCUSDT",
      "direction": "long",
      "entry_price": 50000,
      "stop_loss": 49000,
      "take_profit": 52000,
      "score": 0.85
    }
  ]
}
```

#### Get Trading Signals
```http
GET /api/trading/signals
Authorization: Bearer your_token_here

Response:
{
  "signals": [
    {
      "symbol": "ETHUSDT",
      "type": "buy",
      "price": 3000,
      "timestamp": "2024-01-20T12:00:00Z",
      "confidence": 0.9
    }
  ]
}
```

## Development Guidelines

### Code Review Process
1. **Pull Request Template**
   ```markdown
   ## Description
   [Describe your changes]

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] Unit tests added
   - [ ] Integration tests added
   - [ ] Manual testing completed

   ## Documentation
   - [ ] README updated
   - [ ] API documentation updated
   - [ ] Code comments added
   ```

2. **Review Checklist**
   - Code follows style guide
   - Tests are included
   - Documentation is updated
   - No security vulnerabilities
   - Performance impact considered

### Branch Naming Convention
- Feature: `feature/description`
- Bugfix: `bugfix/description`
- Hotfix: `hotfix/description`
- Release: `release/version`

### Release Process
1. **Version Management**
   ```bash
   # Update version
   npm version patch  # 0.0.1 -> 0.0.2
   npm version minor  # 0.1.0 -> 0.2.0
   npm version major  # 1.0.0 -> 2.0.0
   ```

2. **Release Steps**
   ```bash
   # Create release branch
   git checkout -b release/v1.0.0

   # Update changelog
   ./scripts/update_changelog.sh

   # Create release
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

### Code Style
1. **Python**
   ```python
   # Follow PEP 8
   # Use type hints
   def calculate_position_size(
       account_balance: float,
       risk_per_trade: float
   ) -> float:
       return account_balance * risk_per_trade
   ```

2. **JavaScript/TypeScript**
   ```typescript
   // Use ESLint and Prettier
   // Follow Airbnb style guide
   interface TradingSignal {
     symbol: string;
     type: 'buy' | 'sell';
     price: number;
     timestamp: Date;
   }
   ```

## Dependencies

In addition to the Python dependencies listed in `requirements.txt` (which now includes `pyyaml`), the frontend requires Node.js and npm.