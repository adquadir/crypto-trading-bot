-- Historical Signal Tracking Tables
-- This enables real signal replay backtesting

CREATE TABLE IF NOT EXISTS historical_signals (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Signal Details
    symbol VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50),
    
    -- Price Levels
    entry_price DECIMAL(20,8) NOT NULL,
    stop_loss DECIMAL(20,8) NOT NULL,
    take_profit DECIMAL(20,8) NOT NULL,
    
    -- Signal Quality
    confidence DECIMAL(5,4) NOT NULL,
    risk_reward_ratio DECIMAL(10,4),
    
    -- Market Context
    market_regime VARCHAR(20),
    funding_rate DECIMAL(10,8),
    open_interest BIGINT,
    volume_24h DECIMAL(20,8),
    
    -- Signal Source
    trading_mode VARCHAR(20),
    source_system VARCHAR(50) DEFAULT 'opportunity_manager',
    
    -- Outcome Tracking
    status VARCHAR(20) DEFAULT 'active',
    actual_exit_price DECIMAL(20,8),
    actual_exit_time TIMESTAMP,
    actual_pnl DECIMAL(20,8),
    actual_return_pct DECIMAL(10,6),
    trade_duration_minutes INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_historical_signals_symbol ON historical_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_historical_signals_strategy ON historical_signals(strategy);
CREATE INDEX IF NOT EXISTS idx_historical_signals_timestamp ON historical_signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_historical_signals_status ON historical_signals(status);
