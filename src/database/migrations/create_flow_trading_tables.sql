-- Flow Trading Tables for PostgreSQL
-- Drop existing tables if they exist
DROP TABLE IF EXISTS flow_performance CASCADE;
DROP TABLE IF EXISTS strategy_switches CASCADE;
DROP TABLE IF EXISTS grid_configurations CASCADE;
DROP TABLE IF EXISTS flow_positions CASCADE;

-- Flow trading positions (supports multiple per symbol)
CREATE TABLE flow_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(20) NOT NULL, -- 'scalping' or 'grid_trading'
    entry_price DECIMAL(20,8) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'FILLED', 'CANCELLED'
    order_id VARCHAR(100) NULL,
    grid_level INTEGER NULL, -- for grid trades
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP NULL
);

-- Strategy switches log
CREATE TABLE strategy_switches (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    from_strategy VARCHAR(20) NOT NULL,
    to_strategy VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL,
    market_regime VARCHAR(20) NOT NULL,
    switch_count INTEGER DEFAULT 1,
    performance_score DECIMAL(10,4) NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grid configurations per symbol
CREATE TABLE grid_configurations (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    center_price DECIMAL(20,8) NOT NULL,
    grid_spacing DECIMAL(20,8) NOT NULL,
    levels_count INTEGER NOT NULL DEFAULT 5,
    position_size_usd DECIMAL(10,2) NOT NULL DEFAULT 50.00,
    spacing_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    max_spread_pct DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    breakout_threshold_pct DECIMAL(5,2) NOT NULL DEFAULT 3.0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flow trading performance tracking
CREATE TABLE flow_performance (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(20) NOT NULL, -- 'scalping' or 'grid_trading'
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_pnl DECIMAL(20,8) DEFAULT 0,
    trades_count INTEGER DEFAULT 0,
    win_rate DECIMAL(5,4) DEFAULT 0, -- 0.0 to 1.0
    avg_profit DECIMAL(20,8) DEFAULT 0,
    max_drawdown DECIMAL(20,8) DEFAULT 0,
    total_volume DECIMAL(20,8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_flow_positions_symbol_strategy ON flow_positions(symbol, strategy_type);
CREATE INDEX IF NOT EXISTS idx_flow_positions_status ON flow_positions(status);
CREATE INDEX IF NOT EXISTS idx_flow_positions_created_at ON flow_positions(created_at);

CREATE INDEX IF NOT EXISTS idx_strategy_switches_symbol ON strategy_switches(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_switches_timestamp ON strategy_switches(timestamp);
CREATE INDEX IF NOT EXISTS idx_strategy_switches_transition ON strategy_switches(from_strategy, to_strategy);

CREATE INDEX IF NOT EXISTS idx_grid_configurations_symbol_active ON grid_configurations(symbol, active);
CREATE INDEX IF NOT EXISTS idx_flow_performance_symbol_date ON flow_performance(symbol, date);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER flow_positions_updated_at
    BEFORE UPDATE ON flow_positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER grid_configurations_updated_at
    BEFORE UPDATE ON grid_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER flow_performance_updated_at
    BEFORE UPDATE ON flow_performance
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
 