import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from market_data.exchange_client import ExchangeClient
from strategy.strategy_manager import StrategyManager
from risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)

class OpportunityManager:
    """Manages trading opportunities and their evaluation."""
    
    def __init__(self, exchange_client: ExchangeClient, strategy_manager: StrategyManager, risk_manager: RiskManager):
        """Initialize the opportunity manager."""
        self.exchange_client = exchange_client
        self.strategy_manager = strategy_manager
        self.risk_manager = risk_manager
        self.opportunities: Dict[str, Any] = {}
        
    def get_opportunities(self) -> Dict[str, Any]:
        """Get all current trading opportunities."""
        return self.opportunities
        
    async def scan_opportunities(self) -> None:
        """Scan for new trading opportunities."""
        try:
            # Get active strategies
            active_strategies = self.strategy_manager.get_active_strategies()
            if not active_strategies:
                logger.warning("No active strategies found")
                return
                
            # Get all symbols
            symbols = await self.exchange_client.get_all_symbols()
            if not symbols:
                logger.warning("No symbols found")
                return
                
            # Scan each symbol with each strategy
            for symbol in symbols:
                for strategy_name, strategy in active_strategies.items():
                    try:
                        # Get market data
                        market_data = await self.exchange_client.get_market_data(symbol)
                        if not market_data:
                            continue
                            
                        # Evaluate opportunity
                        opportunity = await self._evaluate_opportunity(symbol, strategy, market_data)
                        if opportunity:
                            self.opportunities[symbol] = opportunity
                            
                    except Exception as e:
                        logger.error(f"Error scanning {symbol} with {strategy_name}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
            
    async def _evaluate_opportunity(self, symbol: str, strategy: Dict[str, Any], market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate a trading opportunity."""
        try:
            # Get strategy parameters
            params = strategy.get('parameters', {})
            
            # Check risk limits
            if not self.risk_manager.check_risk_limits(symbol, market_data):
                return None
                
            # Calculate opportunity metrics
            metrics = {
                'symbol': symbol,
                'strategy': strategy['name'],
                'timestamp': datetime.now().timestamp(),
                'price': market_data.get('price', 0),
                'volume': market_data.get('volume', 0),
                'volatility': market_data.get('volatility', 0),
                'spread': market_data.get('spread', 0),
                'score': 0.0
            }
            
            # Calculate opportunity score
            score = self._calculate_opportunity_score(metrics, params)
            metrics['score'] = score
            
            # Only return opportunities with positive score
            if score > 0:
                return metrics
            return None
            
        except Exception as e:
            logger.error(f"Error evaluating opportunity for {symbol}: {e}")
            return None
            
    def _calculate_opportunity_score(self, metrics: Dict[str, Any], params: Dict[str, Any]) -> float:
        """Calculate opportunity score based on metrics and parameters."""
        try:
            score = 0.0
            
            # Volume score
            if metrics['volume'] > params.get('min_volume', 0):
                score += 1.0
                
            # Volatility score
            volatility = metrics['volatility']
            min_vol = params.get('min_volatility', 0)
            max_vol = params.get('max_volatility', float('inf'))
            if min_vol <= volatility <= max_vol:
                score += 1.0
                
            # Spread score
            if metrics['spread'] < params.get('max_spread', float('inf')):
                score += 1.0
                
            return score
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score: {e}")
            return 0.0 

    async def initialize(self):
        """Async initialization hook for compatibility with bot startup."""
        pass 