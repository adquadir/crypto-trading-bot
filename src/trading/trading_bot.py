from typing import List, Dict, Any
import time
from trading.trading_opportunity import TradingOpportunity
from utils.logger import logger

class TradingBot:
    def __init__(self, exchange_client):
        self.exchange_client = exchange_client
        self.opportunities = {}

    async def _process_signals(self, symbol: str, signals: List[Dict[str, Any]]) -> None:
        """Process trading signals.
        
        Args:
            symbol: Trading pair symbol
            signals: List of trading signals
        """
        try:
            for signal in signals:
                # Get data freshness
                data_freshness = self.exchange_client.get_data_freshness(symbol)
                
                # Create trading opportunity
                opportunity = TradingOpportunity(
                    symbol=signal['symbol'],
                    signal_type=signal['signal_type'],
                    entry_price=signal['entry_price'],
                    stop_loss=signal['stop_loss'],
                    take_profit=signal['take_profit'],
                    confidence=signal['confidence'],
                    timestamp=int(time.time() * 1000),
                    regime=signal['regime'],
                    mtf_alignment=signal.get('mtf_alignment'),
                    data_freshness=data_freshness
                )
                
                # Store opportunity
                self.opportunities[symbol] = opportunity
                
                # Log opportunity
                logger.info(
                    f"New trading opportunity for {symbol}: "
                    f"{opportunity.signal_type} at {opportunity.entry_price} "
                    f"(confidence: {opportunity.confidence:.2f}, "
                    f"regime: {opportunity.regime})"
                )
                
                # Emit opportunity event
                await self.emit_opportunity(opportunity)
                
        except Exception as e:
            logger.error(f"Error processing signals for {symbol}: {str(e)}") 