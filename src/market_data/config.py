"""Configuration settings for market data components."""

config = {
    # Cache TTLs (in seconds)
    'ohlcv_cache_ttl': 60,  # 1 minute
    'orderbook_cache_ttl': 5,  # 5 seconds
    'ticker_cache_ttl': 5,  # 5 seconds
    'trades_cache_ttl': 5,  # 5 seconds
    'open_interest_cache_ttl': 60,  # 1 minute
    'funding_rate_cache_ttl': 300,  # 5 minutes
    'volatility_cache_ttl': 300,  # 5 minutes

    # WebSocket settings
    'ws_reconnect_delay': 1000,  # 1 second
    'ws_max_reconnect_attempts': 10,
    'ws_heartbeat_interval': 30000,  # 30 seconds

    # API settings
    'api_timeout': 10,  # 10 seconds
    'api_max_retries': 3,
    'api_retry_delay': 1000,  # 1 second

    # Rate limiting
    'rate_limit_requests': 1200,  # requests per minute
    'rate_limit_orders': 50,  # orders per 10 seconds
    'rate_limit_weight': 1200,  # weight per minute

    # Data validation
    'min_volume_threshold': 1000000,  # $1M 24h volume
    'max_spread_threshold': 0.002,  # 0.2%
    'min_liquidity_threshold': 100000,  # $100K order book depth
    'max_slippage_threshold': 0.001,  # 0.1%

    # Trading settings
    'min_risk_reward': 1.5,
    'max_position_size': 0.1,  # 10% of portfolio
    'max_leverage': 20,
    'min_confidence': 0.7,
    'max_drawdown': 0.1,  # 10%

    # Volatility thresholds
    'high_volatility_threshold': 0.03,  # 3%
    'medium_volatility_threshold': 0.015,  # 1.5%
    'low_volatility_threshold': 0.005,  # 0.5%

    # Timeframes
    'timeframes': ['1m', '5m', '15m', '1h', '4h', '1d'],
    'default_timeframe': '1m',

    # Logging
    'log_level': 'INFO',
    'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_file': 'logs/market_data.log'
} 