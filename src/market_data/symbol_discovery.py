from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from src.market_data.exchange_client import ExchangeClient
from src.signals.signal_generator import SignalGenerator

logger = logging.getLogger(__name__)

@dataclass
class TradingOpportunity:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float
    leverage: float
    risk_reward: float
    volume_24h: float
    volatility: float
    score: float
    indicators: Dict
    reasoning: List[str]

class SymbolDiscovery:
    def __init__(self, exchange_client: ExchangeClient):
        self.exchange_client = exchange_client
        self.signal_generator = SignalGenerator()
        self.min_volume_24h = 1000000  # Minimum 24h volume in USDT
        self.min_confidence = 0.7  # Minimum signal confidence
        self.min_risk_reward = 2.0  # Minimum risk-reward ratio
        self.max_leverage = 20.0  # Maximum leverage
        self.opportunities: Dict[str, TradingOpportunity] = {}
        
        # Advanced filtering parameters
        self.min_market_cap = 100000000  # Minimum market cap in USDT
        self.max_spread = 0.002  # Maximum spread (0.2%)
        self.min_liquidity = 500000  # Minimum liquidity in USDT
        self.max_correlation = 0.7  # Maximum correlation with existing positions
        self.min_volatility = 0.01  # Minimum volatility (1%)
        self.max_volatility = 0.05  # Maximum volatility (5%)
        
    async def discover_symbols(self) -> List[str]:
        """Fetch all available futures trading pairs from Binance."""
        try:
            exchange_info = await self.exchange_client.get_exchange_info()
            futures_symbols = [
                symbol['symbol'] for symbol in exchange_info['symbols']
                if symbol['status'] == 'TRADING' and symbol['contractType'] == 'PERPETUAL'
            ]
            logger.info(f"Discovered {len(futures_symbols)} trading pairs")
            return futures_symbols
        except Exception as e:
            logger.error(f"Error discovering symbols: {e}")
            return []

    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Fetch comprehensive market data for a symbol."""
        try:
            # Get OHLCV data
            ohlcv = await self.exchange_client.get_historical_data(
                symbol, interval="1m", limit=200
            )
            
            # Get funding rate
            funding_rate = await self.exchange_client.get_funding_rate(symbol)
            
            # Get 24h statistics
            ticker_24h = await self.exchange_client.get_ticker_24h(symbol)
            
            # Get order book
            orderbook = await self.exchange_client.get_orderbook(symbol, limit=10)
            
            return {
                'symbol': symbol,
                'ohlcv': ohlcv,
                'funding_rate': funding_rate,
                'volume_24h': float(ticker_24h['volume']),
                'price_change_24h': float(ticker_24h['priceChangePercent']),
                'orderbook': orderbook
            }
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    def calculate_volatility(self, ohlcv: List[Dict]) -> float:
        """Calculate price volatility."""
        closes = [float(candle['close']) for candle in ohlcv]
        returns = np.diff(closes) / closes[:-1]
        return np.std(returns) * np.sqrt(24 * 60)  # Annualized volatility

    def calculate_opportunity_score(self, opportunity: TradingOpportunity) -> float:
        """Calculate a comprehensive score for the trading opportunity."""
        try:
            # Base score from signal confidence (30%)
            score = opportunity.confidence * 0.3
            
            # Volume factor (15%)
            volume_score = min(opportunity.volume_24h / self.min_volume_24h, 2.0)
            score += volume_score * 0.15
            
            # Risk-reward factor (15%)
            rr_score = min(opportunity.risk_reward / self.min_risk_reward, 3.0)
            score += rr_score * 0.15
            
            # Volatility factor (10%)
            vol_score = 1.0 - abs(opportunity.volatility - 0.03) / 0.03  # Target 3% volatility
            score += vol_score * 0.1
            
            # Leverage factor (5%)
            lev_score = 1.0 - (opportunity.leverage / self.max_leverage)
            score += lev_score * 0.05
            
            # Technical indicators (25%)
            tech_score = self._calculate_technical_score(opportunity.indicators)
            score += tech_score * 0.25
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score: {e}")
            return 0.0
            
    def _calculate_technical_score(self, indicators: Dict) -> float:
        """Calculate score based on technical indicators."""
        try:
            score = 0.0
            weights = {
                'trend': 0.3,
                'momentum': 0.25,
                'volatility': 0.2,
                'volume': 0.15,
                'support_resistance': 0.1
            }
            
            # Trend indicators
            if 'macd' in indicators:
                macd = indicators['macd']
                if macd['value'] > macd['signal'] and macd['histogram'] > 0:
                    score += weights['trend'] * 1.0
                elif macd['value'] < macd['signal'] and macd['histogram'] < 0:
                    score += weights['trend'] * 1.0
                    
            if 'ema' in indicators:
                ema = indicators['ema']
                if ema['fast'] > ema['slow']:
                    score += weights['trend'] * 0.5
                    
            # Momentum indicators
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                if rsi < 30 or rsi > 70:  # Oversold or overbought
                    score += weights['momentum'] * 1.0
                elif 40 <= rsi <= 60:  # Neutral
                    score += weights['momentum'] * 0.5
                    
            if 'stoch' in indicators:
                stoch = indicators['stoch']
                if stoch['k'] < 20 or stoch['k'] > 80:
                    score += weights['momentum'] * 0.5
                    
            # Volatility indicators
            if 'bb' in indicators:
                bb = indicators['bb']
                bb_width = (bb['upper'] - bb['lower']) / bb['middle']
                if bb_width < 0.02:  # Tight bands
                    score += weights['volatility'] * 1.0
                elif bb_width < 0.05:  # Moderate bands
                    score += weights['volatility'] * 0.5
                    
            if 'atr' in indicators:
                atr = indicators['atr']
                if 0.01 <= atr <= 0.03:  # Ideal volatility range
                    score += weights['volatility'] * 1.0
                    
            # Volume indicators
            if 'obv' in indicators:
                obv = indicators['obv']
                if obv['trend'] == 'up':
                    score += weights['volume'] * 1.0
                    
            if 'vwap' in indicators:
                vwap = indicators['vwap']
                if vwap['price'] > vwap['value']:
                    score += weights['volume'] * 0.5
                    
            # Support/Resistance
            if 'sr' in indicators:
                sr = indicators['sr']
                if sr['price'] > sr['support'] and sr['price'] < sr['resistance']:
                    score += weights['support_resistance'] * 1.0
                    
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating technical score: {e}")
            return 0.0
            
    async def scan_opportunities(self, risk_per_trade: float = 50.0) -> List[TradingOpportunity]:
        """Scan all symbols for trading opportunities."""
        try:
            # Get all available symbols
            symbols = await self.discover_symbols()
            
            # Process symbols in parallel
            tasks = [self.get_market_data(symbol) for symbol in symbols]
            market_data_list = await asyncio.gather(*tasks)
            
            opportunities = []
            for market_data in market_data_list:
                if not market_data:
                    continue
                    
                # Apply advanced filters
                if not self._apply_advanced_filters(market_data):
                    continue
                
                # Generate signals
                signals = self.signal_generator.generate_signals(
                    market_data['ohlcv'],
                    market_data['funding_rate']
                )
                
                if not signals:
                    continue
                
                # Calculate volatility
                volatility = self.calculate_volatility(market_data['ohlcv'])
                
                # Process each signal
                for signal in signals:
                    if signal['confidence'] < self.min_confidence:
                        continue
                    
                    # Calculate position parameters
                    entry_price = float(signal['price'])
                    direction = signal['direction']
                    
                    # Calculate stop loss and take profit
                    atr = volatility * entry_price  # Using volatility as ATR proxy
                    stop_loss = entry_price - (2 * atr) if direction == 'LONG' else entry_price + (2 * atr)
                    take_profit = entry_price + (4 * atr) if direction == 'LONG' else entry_price - (4 * atr)
                    
                    # Calculate leverage based on risk
                    risk_amount = abs(entry_price - stop_loss)
                    leverage = min(risk_per_trade / risk_amount, self.max_leverage)
                    
                    # Calculate risk-reward ratio
                    risk_reward = abs(take_profit - entry_price) / abs(entry_price - stop_loss)
                    
                    if risk_reward < self.min_risk_reward:
                        continue
                    
                    opportunity = TradingOpportunity(
                        symbol=market_data['symbol'],
                        direction=direction,
                        entry_price=entry_price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        confidence=signal['confidence'],
                        leverage=leverage,
                        risk_reward=risk_reward,
                        volume_24h=market_data['volume_24h'],
                        volatility=volatility,
                        score=0.0,  # Will be calculated below
                        indicators=signal.get('indicators', {}),
                        reasoning=signal.get('reasoning', [])
                    )
                    
                    # Calculate final score
                    opportunity.score = self.calculate_opportunity_score(opportunity)
                    opportunities.append(opportunity)
            
            # Sort opportunities by score
            opportunities.sort(key=lambda x: x.score, reverse=True)
            
            # Update opportunities dictionary
            self.opportunities = {opp.symbol: opp for opp in opportunities}
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
            return []
            
    def _apply_advanced_filters(self, market_data: Dict) -> bool:
        """Apply advanced filters to market data."""
        try:
            # Volume filter
            if market_data['volume_24h'] < self.min_volume_24h:
                return False
                
            # Spread filter
            if market_data.get('spread', 0) > self.max_spread:
                return False
                
            # Liquidity filter
            if market_data.get('liquidity', 0) < self.min_liquidity:
                return False
                
            # Volatility filter
            volatility = self.calculate_volatility(market_data['ohlcv'])
            if not (self.min_volatility <= volatility <= self.max_volatility):
                return False
                
            # Market cap filter
            if market_data.get('market_cap', 0) < self.min_market_cap:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error applying advanced filters: {e}")
            return False

    def get_top_opportunities(self, count: int = 5) -> List[TradingOpportunity]:
        """Get the top N trading opportunities."""
        opportunities = list(self.opportunities.values())
        opportunities.sort(key=lambda x: x.score, reverse=True)
        return opportunities[:count]

    async def update_opportunities(self, risk_per_trade: float = 50.0):
        """Update opportunities periodically."""
        while True:
            try:
                await self.scan_opportunities(risk_per_trade)
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Error updating opportunities: {e}")
                await asyncio.sleep(5)  # Wait before retrying 