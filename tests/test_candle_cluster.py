"""Tests for candle cluster detection functionality."""

import numpy as np
import pandas as pd
import pytest

from src.strategies.candle_cluster.detector import CandleClusterDetector


@pytest.fixture
def detector():
    """Create a CandleClusterDetector instance for testing."""
    return CandleClusterDetector()


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    # Create a DataFrame with 20 candles
    np.random.seed(42)  # Set a seed for reproducibility
    data = pd.DataFrame({
        'open': np.random.uniform(100, 110, 20),
        'high': np.random.uniform(110, 120, 20),
        'low': np.random.uniform(90, 100, 20),
        'close': np.random.uniform(100, 110, 20),
        'volume': np.random.uniform(1000, 2000, 20)
    })
    return data


@pytest.fixture
def hovering_data():
    """Create sample data showing a hovering pattern."""
    # Create a tight range of prices
    np.random.seed(123)  # Set a seed for reproducibility
    base_price = 100
    range_size = 0.5  # Small range for hovering
    data = pd.DataFrame({
        'open': [
            base_price + np.random.uniform(-range_size, range_size)
            for _ in range(20)
        ],
        'high': [
            base_price + np.random.uniform(0, range_size)
            for _ in range(20)
        ],
        'low': [
            base_price + np.random.uniform(-range_size, 0)
            for _ in range(20)
        ],
        'close': [
            base_price + np.random.uniform(-range_size, range_size)
            for _ in range(20)
        ],
        'volume': [
            1000 + np.random.uniform(-100, 100)
            for _ in range(20)
        ]  # Stable volume
    })
    return data


def test_detector_initialization(detector):
    """Test that the detector initializes correctly."""
    assert detector is not None


def test_detect_with_insufficient_data(detector):
    """Test detection with insufficient data."""
    # Create minimal data
    data = pd.DataFrame({
        'open': [100],
        'high': [101],
        'low': [99],
        'close': [100],
        'volume': [1000]
    })
    
    indicators = {
        'close_prices': data['close'].tolist(),
        'high_prices': data['high'].tolist(),
        'low_prices': data['low'].tolist(),
        'open_prices': data['open'].tolist(),
        'atr': 1.0,
        'atr_trend': 0,
        'recent_volumes': data['volume'].tolist(),
        'avg_recent_volume': 1000,
        'overall_avg_volume': 1000,
        'current_price': 100
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    assert result is None


def test_detect_hovering_buy(detector, hovering_data):
    """Test detection of a hovering BUY opportunity."""
    # Calculate ATR and other indicators
    atr = 0.5  # Small ATR for hovering
    indicators = {
        'close_prices': hovering_data['close'].tolist(),
        'high_prices': hovering_data['high'].tolist(),
        'low_prices': hovering_data['low'].tolist(),
        'open_prices': hovering_data['open'].tolist(),
        'atr': atr,
        'atr_trend': -0.1,  # Decreasing volatility
        'recent_volumes': hovering_data['volume'].tolist(),
        'avg_recent_volume': 1000,
        'overall_avg_volume': 1200,  # Recent volume lower than overall
        'current_price': 99.5  # Near the bottom of the range
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    
    assert result is not None
    assert result['signal_type'] == 'SAFE_BUY'
    assert result['entry'] == 99.5
    assert result['take_profit'] > result['entry']
    assert result['stop_loss'] < result['entry']
    assert 0.6 <= result['confidence_score'] <= 1.0


def test_detect_hovering_sell(detector, hovering_data):
    """Test detection of a hovering SELL opportunity."""
    # Calculate ATR and other indicators
    atr = 0.5  # Small ATR for hovering
    indicators = {
        'close_prices': hovering_data['close'].tolist(),
        'high_prices': hovering_data['high'].tolist(),
        'low_prices': hovering_data['low'].tolist(),
        'open_prices': hovering_data['open'].tolist(),
        'atr': atr,
        'atr_trend': -0.1,  # Decreasing volatility
        'recent_volumes': hovering_data['volume'].tolist(),
        'avg_recent_volume': 1000,
        'overall_avg_volume': 1200,  # Recent volume lower than overall
        'current_price': 100.5  # Near the top of the range
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    
    assert result is not None
    assert result['signal_type'] == 'SAFE_SELL'
    assert result['entry'] == 100.5
    assert result['take_profit'] < result['entry']
    assert result['stop_loss'] > result['entry']
    assert 0.6 <= result['confidence_score'] <= 1.0


def test_no_hovering_detected(detector, sample_data):
    """Test that no hovering is detected in volatile data."""
    # Calculate ATR and other indicators
    atr = 2.0  # Larger ATR for volatile data
    indicators = {
        'close_prices': sample_data['close'].tolist(),
        'high_prices': sample_data['high'].tolist(),
        'low_prices': sample_data['low'].tolist(),
        'open_prices': sample_data['open'].tolist(),
        'atr': atr,
        'atr_trend': 0.1,  # Increasing volatility
        'recent_volumes': sample_data['volume'].tolist(),
        'avg_recent_volume': 2000,
        'overall_avg_volume': 1500,  # Recent volume higher than overall
        'current_price': 105.0
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    assert result is None


def test_risk_reward_ratio(detector, hovering_data):
    """Test that detected opportunities have appropriate risk-reward ratios."""
    atr = 0.5
    indicators = {
        'close_prices': hovering_data['close'].tolist(),
        'high_prices': hovering_data['high'].tolist(),
        'low_prices': hovering_data['low'].tolist(),
        'open_prices': hovering_data['open'].tolist(),
        'atr': atr,
        'atr_trend': -0.1,
        'recent_volumes': hovering_data['volume'].tolist(),
        'avg_recent_volume': 1000,
        'overall_avg_volume': 1200,
        'current_price': 99.5
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    
    if result:
        # Calculate risk-reward ratio
        risk = abs(result['entry'] - result['stop_loss'])
        reward = abs(result['take_profit'] - result['entry'])
        risk_reward_ratio = reward / risk
        
        # Risk-reward should be at least 2:1
        assert risk_reward_ratio >= 2.0


def test_confidence_score_calculation(detector, hovering_data):
    """Test that confidence scores are calculated correctly."""
    atr = 0.5
    indicators = {
        'close_prices': hovering_data['close'].tolist(),
        'high_prices': hovering_data['high'].tolist(),
        'low_prices': hovering_data['low'].tolist(),
        'open_prices': hovering_data['open'].tolist(),
        'atr': atr,
        'atr_trend': -0.1,
        'recent_volumes': hovering_data['volume'].tolist(),
        'avg_recent_volume': 1000,
        'overall_avg_volume': 1200,
        'current_price': 99.5
    }
    
    result = detector.detect('BTCUSDT', indicators, {})
    
    if result:
        # Confidence score should be between 0.6 and 1.0
        assert 0.6 <= result['confidence_score'] <= 1.0
        
        # Lower ATR should result in higher confidence
        indicators['atr'] = 0.3
        result_lower_atr = detector.detect('BTCUSDT', indicators, {})
        if result_lower_atr:
            assert result_lower_atr['confidence_score'] >= result['confidence_score'] 