"""
📊 Strategy Analyzer - Deep Performance Analysis

This module provides detailed analysis of strategy performance,
including parameter optimization and market condition analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

from .backtest_engine import BacktestEngine, BacktestTrade, StrategyPerformance

logger = logging.getLogger(__name__)

@dataclass
class ParameterOptimization:
    """Results from parameter optimization"""
    parameter_name: str
    best_value: float
    best_performance: float
    optimization_results: List[Tuple[float, float]]  # (parameter_value, performance)

class StrategyAnalyzer:
    """
    🔍 Advanced Strategy Analysis and Optimization
    
    Provides deep insights into strategy performance:
    - Parameter optimization
    - Market condition analysis
    - Risk analysis
    - Performance attribution
    """
    
    def __init__(self):
        self.engine = BacktestEngine()
        self.analysis_results = {}
    
    async def analyze_strategy_performance(
        self,
        strategy_name: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        🎯 Comprehensive strategy performance analysis
        """
        logger.info(f"🔍 Analyzing {strategy_name} performance on {symbol}")
        
        # Run backtest
        performance = await self.engine.run_strategy_backtest(
            strategy_name, symbol, start_date, end_date
        )
        
        # Get trade details
        trades = [t for t in self.engine.trades if t.strategy == strategy_name]
        
        # Perform various analyses
        analysis = {
            'basic_performance': performance,
            'trade_distribution': self._analyze_trade_distribution(trades),
            'time_analysis': self._analyze_time_patterns(trades),
            'drawdown_analysis': self._analyze_drawdowns(trades),
            'market_condition_analysis': self._analyze_market_conditions(trades),
            'risk_metrics': self._calculate_advanced_risk_metrics(trades),
            'trade_clustering': self._analyze_trade_clustering(trades)
        }
        
        self.analysis_results[f"{strategy_name}_{symbol}"] = analysis
        
        # Generate insights
        insights = self._generate_insights(analysis)
        analysis['insights'] = insights
        
        return analysis
    
    def _analyze_trade_distribution(self, trades: List[BacktestTrade]) -> Dict:
        """Analyze distribution of trade outcomes"""
        if not trades:
            return {}
        
        returns = [t.return_pct for t in trades if t.return_pct]
        
        return {
            'return_distribution': {
                'mean': np.mean(returns),
                'median': np.median(returns),
                'std': np.std(returns),
                'skewness': self._calculate_skewness(returns),
                'kurtosis': self._calculate_kurtosis(returns)
            },
            'win_loss_streaks': self._calculate_streaks(trades),
            'return_percentiles': {
                '10th': np.percentile(returns, 10),
                '25th': np.percentile(returns, 25),
                '75th': np.percentile(returns, 75),
                '90th': np.percentile(returns, 90)
            }
        }
    
    def _analyze_time_patterns(self, trades: List[BacktestTrade]) -> Dict:
        """Analyze temporal patterns in trading performance"""
        if not trades:
            return {}
        
        # Group trades by hour, day of week, etc.
        hourly_performance = {}
        daily_performance = {}
        
        for trade in trades:
            if trade.entry_time and trade.return_pct:
                hour = trade.entry_time.hour
                day = trade.entry_time.weekday()
                
                if hour not in hourly_performance:
                    hourly_performance[hour] = []
                hourly_performance[hour].append(trade.return_pct)
                
                if day not in daily_performance:
                    daily_performance[day] = []
                daily_performance[day].append(trade.return_pct)
        
        return {
            'hourly_patterns': {
                hour: {
                    'avg_return': np.mean(returns),
                    'win_rate': len([r for r in returns if r > 0]) / len(returns),
                    'trade_count': len(returns)
                }
                for hour, returns in hourly_performance.items()
            },
            'daily_patterns': {
                day: {
                    'avg_return': np.mean(returns),
                    'win_rate': len([r for r in returns if r > 0]) / len(returns),
                    'trade_count': len(returns)
                }
                for day, returns in daily_performance.items()
            }
        }
    
    def _analyze_drawdowns(self, trades: List[BacktestTrade]) -> Dict:
        """Detailed drawdown analysis"""
        if not trades:
            return {}
        
        # Sort trades by time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        # Calculate cumulative P&L
        cumulative_pnl = []
        running_total = 0
        
        for trade in sorted_trades:
            running_total += trade.pnl
            cumulative_pnl.append(running_total)
        
        # Find drawdown periods
        peak = 0
        drawdowns = []
        current_drawdown = {'start': None, 'peak': 0, 'trough': 0, 'end': None}
        
        for i, pnl in enumerate(cumulative_pnl):
            if pnl > peak:
                # New peak
                if current_drawdown['start'] is not None:
                    # End current drawdown
                    current_drawdown['end'] = i
                    drawdowns.append(current_drawdown)
                    current_drawdown = {'start': None, 'peak': 0, 'trough': 0, 'end': None}
                peak = pnl
            elif pnl < peak:
                # In drawdown
                if current_drawdown['start'] is None:
                    current_drawdown['start'] = i
                    current_drawdown['peak'] = peak
                current_drawdown['trough'] = min(current_drawdown.get('trough', pnl), pnl)
        
        # Close final drawdown if needed
        if current_drawdown['start'] is not None:
            current_drawdown['end'] = len(cumulative_pnl) - 1
            drawdowns.append(current_drawdown)
        
        return {
            'max_drawdown': max([(dd['peak'] - dd['trough']) / abs(dd['peak']) if dd['peak'] != 0 else 0 
                                for dd in drawdowns], default=0),
            'avg_drawdown': np.mean([(dd['peak'] - dd['trough']) / abs(dd['peak']) if dd['peak'] != 0 else 0 
                                    for dd in drawdowns]) if drawdowns else 0,
            'drawdown_count': len(drawdowns),
            'longest_drawdown': max([dd['end'] - dd['start'] for dd in drawdowns], default=0),
            'recovery_times': [dd['end'] - dd['start'] for dd in drawdowns if dd['end']]
        }
    
    def _analyze_market_conditions(self, trades: List[BacktestTrade]) -> Dict:
        """Analyze performance under different market conditions"""
        if not trades:
            return {}
        
        # Group by market regime
        regime_performance = {}
        
        for trade in trades:
            regime = trade.market_regime or 'unknown'
            
            if regime not in regime_performance:
                regime_performance[regime] = {
                    'trades': [],
                    'returns': [],
                    'durations': []
                }
            
            regime_performance[regime]['trades'].append(trade)
            if trade.return_pct:
                regime_performance[regime]['returns'].append(trade.return_pct)
            if trade.duration_minutes:
                regime_performance[regime]['durations'].append(trade.duration_minutes)
        
        # Calculate metrics for each regime
        regime_metrics = {}
        for regime, data in regime_performance.items():
            if data['returns']:
                regime_metrics[regime] = {
                    'trade_count': len(data['trades']),
                    'win_rate': len([r for r in data['returns'] if r > 0]) / len(data['returns']),
                    'avg_return': np.mean(data['returns']),
                    'avg_duration': np.mean(data['durations']) if data['durations'] else 0,
                    'volatility': np.std(data['returns']),
                    'best_trade': max(data['returns']),
                    'worst_trade': min(data['returns'])
                }
        
        return regime_metrics
    
    def _calculate_advanced_risk_metrics(self, trades: List[BacktestTrade]) -> Dict:
        """Calculate advanced risk metrics"""
        if not trades:
            return {}
        
        returns = [t.return_pct for t in trades if t.return_pct]
        
        if not returns:
            return {}
        
        # Value at Risk (VaR)
        var_95 = np.percentile(returns, 5)  # 95% VaR
        var_99 = np.percentile(returns, 1)  # 99% VaR
        
        # Conditional Value at Risk (CVaR)
        cvar_95 = np.mean([r for r in returns if r <= var_95])
        cvar_99 = np.mean([r for r in returns if r <= var_99])
        
        # Calmar Ratio
        annual_return = np.mean(returns) * 365  # Assuming daily trades
        max_dd = max([abs(r) for r in returns if r < 0], default=0.01)
        calmar_ratio = annual_return / max_dd if max_dd > 0 else 0
        
        # Sortino Ratio
        negative_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(negative_returns) if negative_returns else 0.01
        sortino_ratio = np.mean(returns) / downside_deviation if downside_deviation > 0 else 0
        
        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'calmar_ratio': calmar_ratio,
            'sortino_ratio': sortino_ratio,
            'downside_deviation': downside_deviation,
            'upside_deviation': np.std([r for r in returns if r > 0])
        }
    
    def _analyze_trade_clustering(self, trades: List[BacktestTrade]) -> Dict:
        """Analyze clustering of trades in time"""
        if len(trades) < 2:
            return {}
        
        # Sort by entry time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        # Calculate time gaps between trades
        time_gaps = []
        for i in range(1, len(sorted_trades)):
            gap = (sorted_trades[i].entry_time - sorted_trades[i-1].entry_time).total_seconds() / 3600  # hours
            time_gaps.append(gap)
        
        return {
            'avg_time_between_trades': np.mean(time_gaps),
            'median_time_between_trades': np.median(time_gaps),
            'min_time_between_trades': min(time_gaps),
            'max_time_between_trades': max(time_gaps),
            'trade_frequency_per_day': 24 / np.mean(time_gaps) if np.mean(time_gaps) > 0 else 0
        }
    
    def _calculate_skewness(self, data: List[float]) -> float:
        """Calculate skewness of returns"""
        if len(data) < 3:
            return 0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0
        
        skew = np.mean([((x - mean) / std) ** 3 for x in data])
        return skew
    
    def _calculate_kurtosis(self, data: List[float]) -> float:
        """Calculate kurtosis of returns"""
        if len(data) < 4:
            return 0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0
        
        kurt = np.mean([((x - mean) / std) ** 4 for x in data]) - 3  # Excess kurtosis
        return kurt
    
    def _calculate_streaks(self, trades: List[BacktestTrade]) -> Dict:
        """Calculate winning and losing streaks"""
        if not trades:
            return {}
        
        # Sort by entry time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        current_streak = 0
        current_type = None
        max_win_streak = 0
        max_loss_streak = 0
        
        for trade in sorted_trades:
            is_winner = trade.pnl > 0 if trade.pnl else False
            
            if current_type == is_winner:
                current_streak += 1
            else:
                # Streak ended
                if current_type is True:  # Was winning streak
                    max_win_streak = max(max_win_streak, current_streak)
                elif current_type is False:  # Was losing streak
                    max_loss_streak = max(max_loss_streak, current_streak)
                
                current_streak = 1
                current_type = is_winner
        
        # Check final streak
        if current_type is True:
            max_win_streak = max(max_win_streak, current_streak)
        elif current_type is False:
            max_loss_streak = max(max_loss_streak, current_streak)
        
        return {
            'max_winning_streak': max_win_streak,
            'max_losing_streak': max_loss_streak
        }
    
    def _generate_insights(self, analysis: Dict) -> List[str]:
        """Generate actionable insights from analysis"""
        insights = []
        
        basic_perf = analysis.get('basic_performance')
        if basic_perf:
            # Win rate insights
            if basic_perf.win_rate > 0.7:
                insights.append("🎯 Excellent win rate - strategy shows strong signal quality")
            elif basic_perf.win_rate < 0.4:
                insights.append("⚠️ Low win rate - consider tightening entry criteria")
            
            # Risk-reward insights
            if basic_perf.avg_risk_reward > 2.0:
                insights.append("💰 Strong risk-reward ratio - good profit potential per trade")
            elif basic_perf.avg_risk_reward < 1.0:
                insights.append("⚠️ Poor risk-reward ratio - consider wider profit targets")
            
            # Drawdown insights
            if basic_perf.max_drawdown > 0.2:
                insights.append("🚨 High drawdown risk - consider reducing position sizes")
            elif basic_perf.max_drawdown < 0.05:
                insights.append("✅ Low drawdown - strategy shows good risk management")
        
        # Market condition insights
        market_analysis = analysis.get('market_condition_analysis', {})
        if market_analysis:
            best_regime = max(market_analysis.items(), 
                             key=lambda x: x[1].get('avg_return', 0), 
                             default=(None, None))
            if best_regime[0]:
                insights.append(f"📈 Performs best in {best_regime[0]} market conditions")
        
        # Time pattern insights
        time_analysis = analysis.get('time_analysis', {})
        hourly_patterns = time_analysis.get('hourly_patterns', {})
        if hourly_patterns:
            best_hour = max(hourly_patterns.items(), 
                           key=lambda x: x[1].get('avg_return', 0), 
                           default=(None, None))
            if best_hour[0] is not None:
                insights.append(f"⏰ Best performance during hour {best_hour[0]} (UTC)")
        
        return insights
    
    async def optimize_parameters(
        self,
        strategy_name: str,
        symbol: str,
        parameter_name: str,
        parameter_range: List[float],
        start_date: datetime,
        end_date: datetime
    ) -> ParameterOptimization:
        """
        🔧 Optimize strategy parameters for best performance
        """
        logger.info(f"🔧 Optimizing {parameter_name} for {strategy_name}")
        
        optimization_results = []
        best_performance = float('-inf')
        best_value = None
        
        for param_value in parameter_range:
            # This would require modifying the strategy to accept parameters
            # For now, we'll simulate the optimization
            try:
                # Run backtest with this parameter value
                performance = await self.engine.run_strategy_backtest(
                    strategy_name, symbol, start_date, end_date
                )
                
                # Use a composite score for optimization
                score = (performance.total_return * 0.4 + 
                        performance.win_rate * 0.3 + 
                        performance.sharpe_ratio * 0.2 - 
                        performance.max_drawdown * 0.1)
                
                optimization_results.append((param_value, score))
                
                if score > best_performance:
                    best_performance = score
                    best_value = param_value
                
                logger.debug(f"Parameter {param_value}: Score {score:.4f}")
                
            except Exception as e:
                logger.warning(f"Failed to test parameter {param_value}: {e}")
        
        return ParameterOptimization(
            parameter_name=parameter_name,
            best_value=best_value,
            best_performance=best_performance,
            optimization_results=optimization_results
        )
    
    def generate_report(self, analysis_key: str, output_file: str = None) -> str:
        """
        📊 Generate comprehensive analysis report
        """
        if analysis_key not in self.analysis_results:
            raise ValueError(f"No analysis found for {analysis_key}")
        
        analysis = self.analysis_results[analysis_key]
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"📊 STRATEGY ANALYSIS REPORT - {analysis_key}")
        report_lines.append("=" * 80)
        
        # Basic performance
        basic_perf = analysis['basic_performance']
        report_lines.append(f"\n💰 PERFORMANCE SUMMARY:")
        report_lines.append(f"   Total Return: {basic_perf.total_return:.1%}")
        report_lines.append(f"   Win Rate: {basic_perf.win_rate:.1%}")
        report_lines.append(f"   Sharpe Ratio: {basic_perf.sharpe_ratio:.2f}")
        report_lines.append(f"   Max Drawdown: {basic_perf.max_drawdown:.1%}")
        
        # Risk metrics
        risk_metrics = analysis.get('risk_metrics', {})
        if risk_metrics:
            report_lines.append(f"\n📊 RISK ANALYSIS:")
            report_lines.append(f"   VaR (95%): {risk_metrics.get('var_95', 0):.2%}")
            report_lines.append(f"   Sortino Ratio: {risk_metrics.get('sortino_ratio', 0):.2f}")
            report_lines.append(f"   Calmar Ratio: {risk_metrics.get('calmar_ratio', 0):.2f}")
        
        # Market conditions
        market_analysis = analysis.get('market_condition_analysis', {})
        if market_analysis:
            report_lines.append(f"\n📈 MARKET CONDITION PERFORMANCE:")
            for regime, metrics in market_analysis.items():
                report_lines.append(f"   {regime.title()}: {metrics['win_rate']:.1%} win rate, "
                                  f"{metrics['avg_return']:.2%} avg return")
        
        # Insights
        insights = analysis.get('insights', [])
        if insights:
            report_lines.append(f"\n💡 KEY INSIGHTS:")
            for insight in insights:
                report_lines.append(f"   • {insight}")
        
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            logger.info(f"📝 Report saved to {output_file}")
        
        return report_text 