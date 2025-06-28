-- Flow Trading Performance Tables
-- Migration: Create flow trading performance tracking tables

-- Flow trading performance summary table
CREATE TABLE IF NOT EXISTS flow_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL, -- 'scalping', 'grid_trading', 'adaptive'
    total_pnl DECIMAL(15, 8) DEFAULT 0.0,
    trades_count INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0.0,
    avg_trade_duration_minutes INTEGER DEFAULT 0,
    max_drawdown_pct DECIMAL(8, 4) DEFAULT 0.0,
    sharpe_ratio DECIMAL(8, 4) DEFAULT 0.0,
    sortino_ratio DECIMAL(8, 4) DEFAULT 0.0,
    profit_factor DECIMAL(8, 4) DEFAULT 0.0,
    total_volume DECIMAL(20, 8) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual flow trading trades table
CREATE TABLE IF NOT EXISTS flow_trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    trade_type VARCHAR(10) NOT NULL, -- 'LONG', 'SHORT'
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(15, 8) DEFAULT 0.0,
    pnl_pct DECIMAL(8, 4) DEFAULT 0.0,
    fees DECIMAL(15, 8) DEFAULT 0.0,
    confidence_score DECIMAL(5, 4) DEFAULT 0.0,
    ml_score DECIMAL(5, 4) DEFAULT 0.0,
    entry_reason TEXT,
    exit_reason VARCHAR(100),
    duration_minutes INTEGER DEFAULT 0,
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grid trading specific performance table
CREATE TABLE IF NOT EXISTS grid_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    grid_id VARCHAR(100) NOT NULL,
    center_price DECIMAL(20, 8) NOT NULL,
    grid_spacing DECIMAL(20, 8) NOT NULL,
    total_levels INTEGER NOT NULL,
    active_levels INTEGER DEFAULT 0,
    filled_levels INTEGER DEFAULT 0,
    total_profit DECIMAL(15, 8) DEFAULT 0.0,
    total_fees DECIMAL(15, 8) DEFAULT 0.0,
    grid_efficiency_score DECIMAL(5, 4) DEFAULT 0.0,
    uptime_minutes INTEGER DEFAULT 0,
    rebalance_count INTEGER DEFAULT 0,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'stopped', 'completed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ML model performance tracking
CREATE TABLE IF NOT EXISTS ml_performance (
    id SERIAL PRIMARY KEY,
    model_type VARCHAR(50) NOT NULL, -- 'signal_generator', 'regime_detector', 'risk_predictor'
    symbol VARCHAR(20),
    prediction_type VARCHAR(50) NOT NULL,
    predicted_value DECIMAL(10, 6),
    actual_value DECIMAL(10, 6),
    accuracy_score DECIMAL(5, 4),
    confidence_score DECIMAL(5, 4),
    feature_importance JSONB,
    model_version VARCHAR(20),
    prediction_time TIMESTAMP NOT NULL,
    validation_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk metrics tracking
CREATE TABLE IF NOT EXISTS risk_metrics (
    id SERIAL PRIMARY KEY,
    portfolio_var_1d DECIMAL(10, 6) DEFAULT 0.0,
    portfolio_var_5d DECIMAL(10, 6) DEFAULT 0.0,
    max_drawdown_pct DECIMAL(8, 4) DEFAULT 0.0,
    sharpe_ratio DECIMAL(8, 4) DEFAULT 0.0,
    sortino_ratio DECIMAL(8, 4) DEFAULT 0.0,
    correlation_concentration DECIMAL(5, 4) DEFAULT 0.0,
    total_exposure_usd DECIMAL(15, 2) DEFAULT 0.0,
    total_exposure_pct DECIMAL(5, 4) DEFAULT 0.0,
    active_strategies INTEGER DEFAULT 0,
    stress_test_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strategy configuration table
CREATE TABLE IF NOT EXISTS strategy_configs (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL UNIQUE,
    strategy_type VARCHAR(50) NOT NULL,
    config_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance alerts table
CREATE TABLE IF NOT EXISTS performance_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL, -- 'performance_degradation', 'risk_breach', 'system_error'
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    symbol VARCHAR(20),
    strategy_type VARCHAR(50),
    message TEXT NOT NULL,
    alert_data JSONB,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System health monitoring
CREATE TABLE IF NOT EXISTS system_health (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'failed'
    cpu_usage_pct DECIMAL(5, 2),
    memory_usage_pct DECIMAL(5, 2),
    response_time_ms INTEGER,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    uptime_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_flow_performance_symbol_date ON flow_performance(symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_flow_trades_symbol_date ON flow_trades(symbol, entry_time);
CREATE INDEX IF NOT EXISTS idx_flow_trades_strategy ON flow_trades(strategy_type, entry_time);
CREATE INDEX IF NOT EXISTS idx_grid_performance_symbol ON grid_performance(symbol, start_time);
CREATE INDEX IF NOT EXISTS idx_ml_performance_model_time ON ml_performance(model_type, prediction_time);
CREATE INDEX IF NOT EXISTS idx_risk_metrics_date ON risk_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_performance_alerts_type_date ON performance_alerts(alert_type, created_at);
CREATE INDEX IF NOT EXISTS idx_system_health_component_date ON system_health(component_name, created_at);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_flow_performance_updated_at BEFORE UPDATE ON flow_performance FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_grid_performance_updated_at BEFORE UPDATE ON grid_performance FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_strategy_configs_updated_at BEFORE UPDATE ON strategy_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
