from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Trade:
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    position_size: float
    leverage: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percentage: float
    stop_loss: float
    take_profit: float
    exit_reason: str  # 'take_profit', 'stop_loss', 'manual', 'liquidation'

class PerformanceTracker:
    def __init__(self):
        self.trades: List[Trade] = []
        self.daily_stats = {}
        self.strategy_stats = {}
        
    def add_trade(self, trade: Trade):
        """Add a completed trade to the history."""
        self.trades.append(trade)
        self._update_stats(trade)
        
    def _update_stats(self, trade: Trade):
        """Update performance statistics."""
        # Update daily stats
        date = trade.exit_time.date()
        if date not in self.daily_stats:
            self.daily_stats[date] = {
                'trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'max_drawdown': 0.0
            }
            
        daily = self.daily_stats[date]
        daily['trades'] += 1
        daily['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            daily['winning_trades'] += 1
        else:
            daily['losing_trades'] += 1
            
        # Update strategy stats
        strategy = f"{trade.direction}_{trade.symbol}"
        if strategy not in self.strategy_stats:
            self.strategy_stats[strategy] = {
                'trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'win_rate': 0.0
            }
            
        strategy_stats = self.strategy_stats[strategy]
        strategy_stats['trades'] += 1
        strategy_stats['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            strategy_stats['winning_trades'] += 1
        else:
            strategy_stats['losing_trades'] += 1
            
        strategy_stats['avg_pnl'] = strategy_stats['total_pnl'] / strategy_stats['trades']
        strategy_stats['win_rate'] = strategy_stats['winning_trades'] / strategy_stats['trades']
        
    def get_performance_metrics(self, days: int = 30) -> Dict:
        """Get performance metrics for the specified period."""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Filter trades within the period
            period_trades = [
                t for t in self.trades
                if start_date <= t.exit_time.date() <= end_date
            ]
            
            if not period_trades:
                return {}
                
            # Calculate metrics
            total_trades = len(period_trades)
            winning_trades = len([t for t in period_trades if t.pnl > 0])
            total_pnl = sum(t.pnl for t in period_trades)
            avg_pnl = total_pnl / total_trades
            
            # Calculate drawdown
            cumulative_pnl = np.cumsum([t.pnl for t in period_trades])
            max_drawdown = 0.0
            peak = cumulative_pnl[0]
            
            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                drawdown = (peak - pnl) / peak if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
                
            # Calculate Sharpe ratio (assuming risk-free rate of 0)
            returns = [t.pnl_percentage for t in period_trades]
            sharpe_ratio = np.mean(returns) / np.std(returns) if len(returns) > 1 else 0
            
            return {
                'period_days': days,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': total_trades - winning_trades,
                'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'strategy_performance': self.strategy_stats
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
            
    def get_strategy_ranking(self) -> List[Dict]:
        """Get ranked list of strategies by performance."""
        try:
            strategies = []
            for strategy, stats in self.strategy_stats.items():
                if stats['trades'] >= 5:  # Minimum 5 trades for ranking
                    strategies.append({
                        'strategy': strategy,
                        'trades': stats['trades'],
                        'win_rate': stats['win_rate'],
                        'total_pnl': stats['total_pnl'],
                        'avg_pnl': stats['avg_pnl']
                    })
                    
            # Sort by total PnL
            return sorted(strategies, key=lambda x: x['total_pnl'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error ranking strategies: {e}")
            return []
            
    def export_trade_history(self, filepath: str):
        """Export trade history to CSV file."""
        try:
            df = pd.DataFrame([vars(trade) for trade in self.trades])
            df.to_csv(filepath, index=False)
        except Exception as e:
            logger.error(f"Error exporting trade history: {e}")
            
    def get_daily_summary(self, date: datetime.date) -> Optional[Dict]:
        """Get summary of trading activity for a specific date."""
        return self.daily_stats.get(date) 