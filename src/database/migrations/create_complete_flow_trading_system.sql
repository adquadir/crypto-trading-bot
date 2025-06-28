-- Complete Flow Trading System Database Migration
-- Creates all tables needed for the enhanced flow trading system

-- Flow Trading Tables
CREATE TABLE IF NOT EXISTS flow_trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    trade_type VARCHAR(10) NOT NULL, -- 'LONG' or 'SHORT'
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 6),
    fees DECIMAL(20, 8) DEFAULT 0,
    confidence_score DECIMAL(5, 4) DEFAULT 0,
    ml_score DECIMAL(5, 4) DEFAULT 0,
    entry_reason TEXT,
    exit_reason VARCHAR(100),
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    duration_minutes INTEGER,
    entry_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flow_trades_symbol ON flow_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_flow_trades_strategy ON flow_trades(strategy_type);
CREATE INDEX IF NOT EXISTS idx_flow_trades_entry_time ON flow_trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_flow_trades_exit_time ON flow_trades(exit_time);

-- Flow Performance Tracking
CREATE TABLE IF NOT EXISTS flow_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    trades_count INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,
    max_drawdown_pct DECIMAL(10, 6) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 6) DEFAULT 0,
    profit_factor DECIMAL(10, 6) DEFAULT 0,
    avg_trade_duration_minutes DECIMAL(10, 2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_performance_symbol_strategy ON flow_performance(symbol, strategy_type);

-- Performance Alerts
CREATE TABLE IF NOT EXISTS performance_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    symbol VARCHAR(20),
    strategy_type VARCHAR(50),
    message TEXT NOT NULL,
    alert_data JSONB,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_performance_alerts_type ON performance_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_performance_alerts_severity ON performance_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_performance_alerts_created ON performance_alerts(created_at);

-- System Health Monitoring
CREATE TABLE IF NOT EXISTS system_health (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'failed'
    cpu_usage_pct DECIMAL(5, 2) DEFAULT 0,
    memory_usage_pct DECIMAL(5, 2) DEFAULT 0,
    response_time_ms DECIMAL(10, 2) DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    uptime_minutes INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_health_component ON system_health(component_name);
CREATE INDEX IF NOT EXISTS idx_system_health_status ON system_health(status);
CREATE INDEX IF NOT EXISTS idx_system_health_created ON system_health(created_at);

-- Flow Trading Signals (Enhanced)
CREATE TABLE IF NOT EXISTS flow_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    signal_type VARCHAR(20) NOT NULL, -- 'BUY', 'SELL', 'HOLD'
    confidence_score DECIMAL(5, 4) NOT NULL,
    ml_score DECIMAL(5, 4),
    price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8),
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    technical_indicators JSONB,
    signal_reason TEXT,
    is_executed BOOLEAN DEFAULT FALSE,
    execution_price DECIMAL(20, 8),
    execution_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flow_signals_symbol ON flow_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_flow_signals_strategy ON flow_signals(strategy_type);
CREATE INDEX IF NOT EXISTS idx_flow_signals_created ON flow_signals(created_at);
CREATE INDEX IF NOT EXISTS idx_flow_signals_executed ON flow_signals(is_executed);

-- ML Training Data
CREATE TABLE IF NOT EXISTS ml_training_data (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES flow_trades(id),
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    features JSONB NOT NULL,
    target_value DECIMAL(10, 6), -- Actual outcome (pnl_pct)
    prediction_value DECIMAL(10, 6), -- ML prediction
    confidence_score DECIMAL(5, 4),
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ml_training_symbol ON ml_training_data(symbol);
CREATE INDEX IF NOT EXISTS idx_ml_training_strategy ON ml_training_data(strategy_type);
CREATE INDEX IF NOT EXISTS idx_ml_training_created ON ml_training_data(created_at);

-- Risk Management Events
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL, -- 'position_limit', 'drawdown_limit', 'exposure_limit'
    symbol VARCHAR(20),
    strategy_type VARCHAR(50),
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    current_value DECIMAL(20, 8),
    limit_value DECIMAL(20, 8),
    action_taken VARCHAR(100),
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);
CREATE INDEX IF NOT EXISTS idx_risk_events_created ON risk_events(created_at);

-- Configuration History
CREATE TABLE IF NOT EXISTS config_history (
    id SERIAL PRIMARY KEY,
    config_type VARCHAR(50) NOT NULL, -- 'scalping', 'risk_management', 'flow_trading'
    symbol VARCHAR(20),
    old_config JSONB,
    new_config JSONB NOT NULL,
    changed_by VARCHAR(100) DEFAULT 'system',
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_history_type ON config_history(config_type);
CREATE INDEX IF NOT EXISTS idx_config_history_created ON config_history(created_at);

-- Market Data Cache (for performance)
CREATE TABLE IF NOT EXISTS market_data_cache (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '5m', '15m', '1h', '4h', '1d'
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_timestamp 
ON market_data_cache(symbol, timeframe, timestamp);

-- Paper Trading Accounts
CREATE TABLE IF NOT EXISTS paper_accounts (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(100) NOT NULL DEFAULT 'default',
    initial_balance DECIMAL(20, 8) NOT NULL DEFAULT 10000.00,
    current_balance DECIMAL(20, 8) NOT NULL DEFAULT 10000.00,
    equity DECIMAL(20, 8) NOT NULL DEFAULT 10000.00,
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,
    profit_factor DECIMAL(10, 6) DEFAULT 0,
    max_drawdown DECIMAL(10, 6) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 6) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strategy Performance by Symbol
CREATE TABLE IF NOT EXISTS strategy_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    total_signals INTEGER DEFAULT 0,
    executed_signals INTEGER DEFAULT 0,
    successful_signals INTEGER DEFAULT 0,
    avg_confidence DECIMAL(5, 4) DEFAULT 0,
    avg_ml_score DECIMAL(5, 4) DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,
    profit_factor DECIMAL(10, 6) DEFAULT 0,
    max_consecutive_wins INTEGER DEFAULT 0,
    max_consecutive_losses INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_performance_unique 
ON strategy_performance(symbol, strategy_type, timeframe);

-- Backtesting Results
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    backtest_name VARCHAR(200) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    initial_balance DECIMAL(20, 8) NOT NULL,
    final_balance DECIMAL(20, 8) NOT NULL,
    total_return_pct DECIMAL(10, 6) NOT NULL,
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    win_rate DECIMAL(5, 4) NOT NULL,
    profit_factor DECIMAL(10, 6) NOT NULL,
    max_drawdown_pct DECIMAL(10, 6) NOT NULL,
    sharpe_ratio DECIMAL(10, 6) NOT NULL,
    sortino_ratio DECIMAL(10, 6) DEFAULT 0,
    calmar_ratio DECIMAL(10, 6) DEFAULT 0,
    avg_trade_duration_minutes DECIMAL(10, 2) DEFAULT 0,
    config_used JSONB,
    detailed_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy ON backtest_results(strategy_type);
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON backtest_results(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created ON backtest_results(created_at);

-- Create views for common queries
CREATE OR REPLACE VIEW v_active_positions AS
SELECT 
    id,
    symbol,
    strategy_type,
    trade_type,
    entry_price,
    quantity,
    confidence_score,
    ml_score,
    entry_reason,
    market_regime,
    volatility_regime,
    entry_time,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - entry_time))/60 as hold_time_minutes
FROM flow_trades 
WHERE exit_time IS NULL;

CREATE OR REPLACE VIEW v_daily_performance AS
SELECT 
    DATE(entry_time) as trade_date,
    symbol,
    strategy_type,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    AVG(confidence_score) as avg_confidence,
    AVG(duration_minutes) as avg_duration
FROM flow_trades 
WHERE exit_time IS NOT NULL
GROUP BY DATE(entry_time), symbol, strategy_type
ORDER BY trade_date DESC;

CREATE OR REPLACE VIEW v_strategy_summary AS
SELECT 
    strategy_type,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100, 2) as win_rate_pct,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    MAX(pnl) as best_trade,
    MIN(pnl) as worst_trade,
    AVG(confidence_score) as avg_confidence,
    AVG(duration_minutes) as avg_duration_minutes
FROM flow_trades 
WHERE exit_time IS NOT NULL
GROUP BY strategy_type
ORDER BY total_pnl DESC;

-- Insert default paper trading account
INSERT INTO paper_accounts (account_name, initial_balance, current_balance, equity) 
VALUES ('default', 10000.00, 10000.00, 10000.00)
ON CONFLICT DO NOTHING;

-- Create functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
CREATE TRIGGER update_flow_trades_updated_at BEFORE UPDATE ON flow_trades 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_paper_accounts_updated_at BEFORE UPDATE ON paper_accounts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_trading_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_trading_user;

COMMIT;
