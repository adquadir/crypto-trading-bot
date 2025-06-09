from datetime import datetime
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.database.database import Database
from src.models import TradingSignal
from src.models.strategy import (
    Strategy,
    StrategyParameters,
    MACDStrategy,
    RSIStrategy,
    BollingerBandsStrategy
)

logger = logging.getLogger(__name__)

class SignalEngine:
    def __init__(self, db: Database):
        self.db = db
        self.strategies: Dict[str, Strategy] = {}
        self._load_strategies()
    
    def _load_strategies(self):
        """Load all active strategies from the database."""
        strategies = self.db.get_all_strategies()
        for strategy in strategies:
            if strategy.is_active:
                self._initialize_strategy(strategy)
    
    def _initialize_strategy(self, strategy: Strategy):
        """Initialize a strategy instance based on its type."""
        params = StrategyParameters(
            name=strategy.name,
            description=strategy.description,
            timeframe=strategy.parameters.get('timeframe', '1h'),
            symbols=strategy.parameters.get('symbols', []),
            parameters=strategy.parameters
        )
        
        if strategy.type == 'macd':
            self.strategies[strategy.name] = MACDStrategy(params)
        elif strategy.type == 'rsi':
            self.strategies[strategy.name] = RSIStrategy(params)
        elif strategy.type == 'bollinger':
            self.strategies[strategy.name] = BollingerBandsStrategy(params)
        else:
            logger.warning(f"Unknown strategy type: {strategy.type}")
    
    def generate_signals(
        self, data: pd.DataFrame, symbol: str
    ) -> List[TradingSignal]:
        """Generate trading signals for a given symbol using all active strategies."""
        signals = []
        for strategy_name, strategy in self.strategies.items():
            try:
                if symbol in strategy.symbols:
                    result = strategy.generate_signals(data)
                    if result['signals']['signal'].iloc[-1] != 0:
                        signal = TradingSignal(
                            strategy_id=strategy_name,
                            symbol=symbol,
                            timestamp=datetime.utcnow(),
                            signal_type=(
                                'BUY' if result['signals']['signal'].iloc[-1] > 0
                                else 'SELL'
                            ),
                            price=data['close'].iloc[-1],
                            confidence=abs(result['signals']['signal'].iloc[-1]),
                            indicators=result['indicators'].to_dict()
                        )
                        signals.append(signal)
            except Exception as e:
                logger.error(
                    f"Error generating signals for {strategy_name}: {str(e)}"
                )
        
        return signals 