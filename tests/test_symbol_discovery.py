"""Tests for symbol discovery functionality."""

from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity
from src.signals.signal_generator import SignalGenerator


@pytest.fixture
def mock_exchange_client():
    """Mock exchange client for testing."""
    mock_client = AsyncMock()
    # Mock get_symbols to return a predefined list for testing discovery
    mock_client.get_symbols.return_value = [
        {
            'symbol': 'BTCUSDT',
            'status': 'TRADING',
            'isSpotTradingAllowed': False,
            'isMarginTradingAllowed': True
        },
        {
            'symbol': 'ETHUSDT',
            'status': 'TRADING',
            'isSpotTradingAllowed': False,
            'isMarginTradingAllowed': True
        },
        {
            'symbol': 'LTCBTC',
            'status': 'TRADING',
            'isSpotTradingAllowed': True,
            'isMarginTradingAllowed': True
        },
        {
            'symbol': 'INVALIDUSDT',
            'status': 'BREAK',
            'isSpotTradingAllowed': False,
            'isMarginTradingAllowed': True
        },
    ]
    # Mock get_candlesticks with some dummy data
    mock_client.get_candlesticks.return_value = pd.DataFrame({
        'open': np.random.rand(100) * 10000 + 40000,
        'high': np.random.rand(100) * 10000 + 40000,
        'low': np.random.rand(100) * 10000 + 40000,
        'close': np.random.rand(100) * 10000 + 40000,
        'volume': np.random.rand(100) * 1000,
        'close_time': pd.to_datetime(np.arange(100), unit='m')
    })
    # Mock other methods used by get_market_data and scoring
    mock_client.get_ticker_24h.return_value = {
        'volume': 100000000,
        'quoteVolume': 100000000,
        'lastPrice': 45000
    }
    mock_client.get_orderbook.return_value = {
        'bids': [['45000', '10']],
        'asks': [['45001', '10']]
    }
    mock_client.get_funding_rate.return_value = {'lastFundingRate': '0.0001'}
    mock_client.get_open_interest.return_value = {'openInterest': '100000'}
    mock_client.get_symbol_info.return_value = {
        'quoteAsset': 'USDT',
        'baseAsset': 'BTC',
        'filters': []
    }
    
    return mock_client


@pytest.fixture
def mock_signal_generator():
    """Mock signal generator for testing."""
    mock_gen = MagicMock(spec=SignalGenerator)
    
    def mock_generate_signals(symbol, indicators, initial_confidence):
        if symbol == 'BTCUSDT':
            return {
                'signal_type': 'BUY',
                'entry': 45000,
                'take_profit': 46000,
                'stop_loss': 44500,
                'confidence_score': 0.8,
                'reasoning': 'Test buy signal'
            }
        elif symbol == 'ETHUSDT':
            return {
                'signal_type': 'SELL',
                'entry': 3000,
                'take_profit': 2900,
                'stop_loss': 3050,
                'confidence_score': 0.7,
                'reasoning': 'Test sell signal'
            }
        else:
            return None
             
    mock_gen.generate_signals.side_effect = mock_generate_signals
    return mock_gen


@pytest.fixture
def symbol_discovery(mock_exchange_client, mock_signal_generator):
    """Create a SymbolDiscovery instance with mocked dependencies."""
    sd = SymbolDiscovery(mock_exchange_client)
    # Manually set the signal generator mock
    sd.signal_generator = mock_signal_generator
    # Mock the internal _get_historical_klines to return the same data
    sd._get_historical_klines = AsyncMock()
    sd._get_historical_klines.return_value = (
        mock_exchange_client.get_candlesticks.return_value
    )
    return sd


@pytest.mark.asyncio
async def test_scan_opportunities_finds_trading_symbols(symbol_discovery):
    """Test that scan_opportunities finds valid trading symbols."""
    opportunities = await symbol_discovery.scan_opportunities()
    
    # Should find BTCUSDT and ETHUSDT based on mock get_symbols
    symbols_found = {opp.symbol for opp in opportunities}
    assert 'BTCUSDT' in symbols_found
    assert 'ETHUSDT' in symbols_found
    # Should not find invalid or spot-only symbols
    assert 'LTCBTC' not in symbols_found
    assert 'INVALIDUSDT' not in symbols_found
    assert len(opportunities) == 2


@pytest.mark.asyncio
async def test_scan_opportunities_applies_filters(symbol_discovery):
    """Test that scan_opportunities applies filters correctly."""
    # Configure filters to be very strict
    symbol_discovery.min_volume_24h = 200000000  # Higher than mocked data
    symbol_discovery.min_technical_score = 1.0  # Higher than mocked data
    
    opportunities = await symbol_discovery.scan_opportunities()
    
    # With strict filters, no opportunities should be found
    assert len(opportunities) == 0


@pytest.mark.asyncio
async def test_process_symbol_generates_opportunity(
    symbol_discovery, mock_exchange_client, mock_signal_generator
):
    """Test that _process_symbol_with_retry generates opportunities correctly."""
    # Use BTCUSDT which is mocked to return a signal
    opportunity = await symbol_discovery._process_symbol_with_retry('BTCUSDT')
    
    assert isinstance(opportunity, TradingOpportunity)
    assert opportunity.symbol == 'BTCUSDT'
    assert opportunity.direction == 'BUY'
    assert opportunity.entry_price == 45000
    assert opportunity.take_profit == 46000
    assert opportunity.stop_loss == 44500
    assert opportunity.confidence == 0.8
    assert opportunity.reasoning == 'Test buy signal'
    
    # Check that market data fetching methods were called
    mock_exchange_client.get_candlesticks.assert_called_once()
    mock_exchange_client.get_ticker_24h.assert_called_once()
    mock_exchange_client.get_orderbook.assert_called_once()
    mock_exchange_client.get_symbol_info.assert_called_once()
    
    # Check that signal_generator was called
    mock_signal_generator.generate_signals.assert_called_once_with(
        'BTCUSDT', MagicMock(), 1.0
    )


@pytest.mark.asyncio
async def test_process_symbol_returns_none_if_no_signal(
    symbol_discovery, mock_exchange_client
):
    """Test that _process_symbol_with_retry returns None when no signal."""
    # Use LTCBTC which is mocked to return None for signal
    opportunity = await symbol_discovery._process_symbol_with_retry('LTCBTC')
    
    assert opportunity is None
    
    # Check that market data fetching methods were called
    mock_exchange_client.get_candlesticks.assert_called_once_with(
        'LTCBTC', '1m', '100'
    )
    mock_exchange_client.get_ticker_24h.assert_called_once()
    mock_exchange_client.get_orderbook.assert_called_once()
    mock_exchange_client.get_symbol_info.assert_called_once()
    
    # Check that signal_generator was called
    symbol_discovery.signal_generator.generate_signals.assert_called_once_with(
        'LTCBTC', MagicMock(), 1.0
    )


@pytest.mark.asyncio
async def test_get_market_data_returns_expected_structure(
    symbol_discovery, mock_exchange_client
):
    """Test that get_market_data returns the expected data structure."""
    # Use BTCUSDT for which candlestick data is mocked
    market_data = await symbol_discovery.get_market_data('BTCUSDT')
    
    assert isinstance(market_data, dict)
    assert 'klines' in market_data
    assert isinstance(market_data['klines'], pd.DataFrame)
    assert 'open' in market_data['klines'].columns
    assert 'close' in market_data['klines'].columns
    assert 'volume' in market_data['klines'].columns
    
    # Check for other expected keys based on mocked data
    assert 'volume_24h' in market_data
    assert 'liquidity' in market_data
    assert 'funding_rate' in market_data
    assert 'open_interest' in market_data
    assert 'quote_asset' in market_data
    assert 'base_asset' in market_data
    
    # Check values from mocks
    assert market_data['volume_24h'] == 100000000
    assert market_data['liquidity'] is not None


@pytest.mark.asyncio
async def test_opportunity_with_confidence_0_5_is_accepted(
    symbol_discovery, mock_signal_generator
):
    """Test that opportunities with confidence 0.5 are accepted."""
    # Set min_confidence to 0.5
    symbol_discovery.min_confidence = 0.5
    
    # Mock generate_signals to return a signal with confidence 0.5
    def mock_generate_signals(symbol, indicators, initial_confidence):
        return {
            'signal_type': 'BUY',
            'entry': 100,
            'take_profit': 110,
            'stop_loss': 95,
            'confidence_score': 0.5,
            'reasoning': 'Test confidence 0.5'
        }
    
    symbol_discovery.signal_generator.generate_signals.side_effect = (
        mock_generate_signals
    )
    
    # Should not be discarded
    opportunity = await symbol_discovery._process_symbol_with_retry('BTCUSDT')
    assert opportunity is not None
    assert opportunity.confidence == 0.5
    assert opportunity.symbol == 'BTCUSDT'

# Add more tests here for specific filtering logic, scoring calculations, edge cases, etc.
# Example: test_scan_opportunities_with_min_score_filter
# Example: test_scan_opportunities_with_min_risk_reward_filter
# Example: test_process_symbol_calculates_risk_reward_correctly
# Example: test_process_symbol_handles_api_errors 