-- ML Learning System Database Schema
-- Creates tables for persistent machine learning across system restarts

-- ML Training Data Table
-- Stores all trade outcomes and features for learning
CREATE TABLE IF NOT EXISTS ml_training_data (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    system_type VARCHAR(20) NOT NULL, -- 'paper_trading' or 'profit_scraping'
    confidence_score FLOAT NOT NULL,
    ml_score FLOAT,
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    pnl_pct FLOAT,
    duration_minutes INTEGER,
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    exit_reason VARCHAR(50),
    success BOOLEAN NOT NULL,
    features JSONB, -- Store all extracted features as JSON
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Strategy Performance Learning Table
-- Tracks performance by strategy, confidence ranges, and market conditions
CREATE TABLE IF NOT EXISTS strategy_performance_learning (
    id SERIAL PRIMARY KEY,
    strategy_type VARCHAR(50) NOT NULL,
    system_type VARCHAR(20) NOT NULL,
    confidence_range VARCHAR(20) NOT NULL, -- '0.5-0.6', '0.6-0.7', etc.
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate FLOAT DEFAULT 0.0,
    avg_pnl_pct FLOAT DEFAULT 0.0,
    avg_duration_minutes FLOAT DEFAULT 0.0,
    total_pnl FLOAT DEFAULT 0.0,
    max_drawdown_pct FLOAT DEFAULT 0.0,
    sharpe_ratio FLOAT DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(strategy_type, system_type, confidence_range, market_regime, volatility_regime)
);

-- Signal Quality Learning Table
-- Tracks how well confidence scores predict actual outcomes
CREATE TABLE IF NOT EXISTS signal_quality_learning (
    id SERIAL PRIMARY KEY,
    signal_type VARCHAR(50) NOT NULL,
    confidence_bucket FLOAT NOT NULL, -- 0.5, 0.6, 0.7, etc. (rounded)
    predicted_success_rate FLOAT NOT NULL,
    actual_success_rate FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    market_conditions JSONB,
    calibration_score FLOAT, -- How well calibrated the confidence is
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(signal_type, confidence_bucket)
);

-- Market Regime Learning Table
-- Learns which strategies work best in different market conditions
CREATE TABLE IF NOT EXISTS market_regime_learning (
    id SERIAL PRIMARY KEY,
    market_regime VARCHAR(50) NOT NULL,
    volatility_regime VARCHAR(50) NOT NULL,
    best_strategy VARCHAR(50),
    best_strategy_win_rate FLOAT,
    total_trades_in_regime INTEGER DEFAULT 0,
    avg_trade_duration_minutes FLOAT DEFAULT 0.0,
    regime_characteristics JSONB,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(market_regime, volatility_regime)
);

-- Position Sizing Learning Table
-- Learns optimal position sizes based on confidence and market conditions
CREATE TABLE IF NOT EXISTS position_sizing_learning (
    id SERIAL PRIMARY KEY,
    confidence_range VARCHAR(20) NOT NULL,
    market_regime VARCHAR(50),
    volatility_regime VARCHAR(50),
    optimal_position_size_pct FLOAT NOT NULL,
    risk_adjusted_return FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(confidence_range, market_regime, volatility_regime)
);

-- Feature Importance Learning Table
-- Tracks which features are most predictive of success
CREATE TABLE IF NOT EXISTS feature_importance_learning (
    id SERIAL PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    importance_score FLOAT NOT NULL,
    correlation_with_success FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(feature_name, strategy_type)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_ml_training_data_symbol_strategy ON ml_training_data(symbol, strategy_type);
CREATE INDEX IF NOT EXISTS idx_ml_training_data_system_type ON ml_training_data(system_type);
CREATE INDEX IF NOT EXISTS idx_ml_training_data_success ON ml_training_data(success);
CREATE INDEX IF NOT EXISTS idx_ml_training_data_created_at ON ml_training_data(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_training_data_confidence ON ml_training_data(confidence_score);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy ON strategy_performance_learning(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_system ON strategy_performance_learning(system_type);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_confidence ON strategy_performance_learning(confidence_range);

CREATE INDEX IF NOT EXISTS idx_signal_quality_type ON signal_quality_learning(signal_type);
CREATE INDEX IF NOT EXISTS idx_signal_quality_confidence ON signal_quality_learning(confidence_bucket);

CREATE INDEX IF NOT EXISTS idx_market_regime_regime ON market_regime_learning(market_regime);
CREATE INDEX IF NOT EXISTS idx_market_regime_volatility ON market_regime_learning(volatility_regime);

-- Data retention policy (keep last 6 months of detailed data)
-- This can be implemented as a scheduled job
-- DELETE FROM ml_training_data WHERE created_at < NOW() - INTERVAL '6 months';
