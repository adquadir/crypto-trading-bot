"""
ML Learning Service
Central service for persistent machine learning across paper trading and profit scraping systems
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

from sqlalchemy import text
from src.database.database import Database

logger = logging.getLogger(__name__)

@dataclass
class TradeOutcome:
    """Represents a completed trade outcome for learning"""
    trade_id: str
    symbol: str
    strategy_type: str
    system_type: str  # 'paper_trading' or 'profit_scraping'
    confidence_score: float
    ml_score: Optional[float]
    entry_price: float
    exit_price: Optional[float]
    pnl_pct: Optional[float]
    duration_minutes: Optional[int]
    market_regime: str
    volatility_regime: str
    exit_reason: str
    success: bool
    features: Dict[str, Any]
    entry_time: datetime
    exit_time: Optional[datetime]

@dataclass
class StrategyPerformance:
    """Strategy performance metrics"""
    strategy_type: str
    system_type: str
    confidence_range: str
    market_regime: str
    volatility_regime: str
    total_trades: int
    winning_trades: int
    win_rate: float
    avg_pnl_pct: float
    avg_duration_minutes: float
    sharpe_ratio: float

@dataclass
class SignalRecommendation:
    """ML recommendation for a trading signal"""
    should_take_trade: bool
    confidence_adjustment: float  # Adjusted confidence based on learning
    recommended_position_size: float
    expected_win_rate: float
    expected_pnl_pct: float
    reasoning: str

class MLLearningService:
    """Central ML learning service for both paper trading and profit scraping"""
    
    def __init__(self):
        self.db = Database()
        self.cache = {
            'strategy_performance': {},
            'signal_quality': {},
            'market_regimes': {},
            'feature_importance': {}
        }
        self.cache_expiry = datetime.now()
        self.cache_duration_minutes = 30
        
        logger.info("🧠 ML Learning Service initialized")
    
    async def initialize(self):
        """Initialize the ML learning service"""
        try:
            # Create ML learning tables if they don't exist
            await self._create_ml_tables()
            
            # Load initial learning data into cache
            await self._refresh_cache()
            
            logger.info("✅ ML Learning Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ML Learning Service: {e}")
            raise
    
    async def store_trade_outcome(self, trade_outcome: TradeOutcome):
        """Store a completed trade outcome for learning"""
        try:
            query = text("""
            INSERT INTO ml_training_data 
            (trade_id, symbol, strategy_type, system_type, confidence_score, ml_score,
             entry_price, exit_price, pnl_pct, duration_minutes, market_regime, 
             volatility_regime, exit_reason, success, features, entry_time, exit_time)
            VALUES (:trade_id, :symbol, :strategy_type, :system_type, :confidence_score, :ml_score,
                    :entry_price, :exit_price, :pnl_pct, :duration_minutes, :market_regime,
                    :volatility_regime, :exit_reason, :success, :features, :entry_time, :exit_time)
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'trade_id': trade_outcome.trade_id,
                    'symbol': trade_outcome.symbol,
                    'strategy_type': trade_outcome.strategy_type,
                    'system_type': trade_outcome.system_type,
                    'confidence_score': trade_outcome.confidence_score,
                    'ml_score': trade_outcome.ml_score,
                    'entry_price': trade_outcome.entry_price,
                    'exit_price': trade_outcome.exit_price,
                    'pnl_pct': trade_outcome.pnl_pct,
                    'duration_minutes': trade_outcome.duration_minutes,
                    'market_regime': trade_outcome.market_regime,
                    'volatility_regime': trade_outcome.volatility_regime,
                    'exit_reason': trade_outcome.exit_reason,
                    'success': trade_outcome.success,
                    'features': json.dumps(trade_outcome.features),
                    'entry_time': trade_outcome.entry_time,
                    'exit_time': trade_outcome.exit_time
                })
            
            # Update strategy performance learning
            await self._update_strategy_performance(trade_outcome)
            
            # Update signal quality learning
            await self._update_signal_quality(trade_outcome)
            
            # Update market regime learning
            await self._update_market_regime_learning(trade_outcome)
            
            logger.info(f"✅ Stored trade outcome: {trade_outcome.trade_id} ({trade_outcome.system_type})")
            
        except Exception as e:
            logger.error(f"Error storing trade outcome: {e}")
    
    async def get_signal_recommendation(self, signal_data: Dict[str, Any]) -> SignalRecommendation:
        """Get ML recommendation for a trading signal"""
        try:
            await self._ensure_cache_fresh()
            
            strategy_type = signal_data.get('strategy_type', 'unknown')
            confidence = signal_data.get('confidence', 0.5)
            market_regime = signal_data.get('market_regime', 'unknown')
            volatility_regime = signal_data.get('volatility_regime', 'medium')
            
            # Get historical performance for similar signals
            performance = await self._get_strategy_performance(
                strategy_type, confidence, market_regime, volatility_regime
            )
            
            # Calibrate confidence score based on historical accuracy
            calibrated_confidence = await self._calibrate_confidence(
                strategy_type, confidence
            )
            
            # Get optimal position size
            optimal_position_size = await self._get_optimal_position_size(
                calibrated_confidence, market_regime, volatility_regime
            )
            
            # Determine if we should take the trade
            should_take_trade = await self._should_take_trade(
                strategy_type, calibrated_confidence, market_regime, performance
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                performance, calibrated_confidence, confidence, should_take_trade
            )
            
            recommendation = SignalRecommendation(
                should_take_trade=should_take_trade,
                confidence_adjustment=calibrated_confidence - confidence,
                recommended_position_size=optimal_position_size,
                expected_win_rate=performance.get('win_rate', 0.5),
                expected_pnl_pct=performance.get('avg_pnl_pct', 0.0),
                reasoning=reasoning
            )
            
            logger.info(f"🎯 Signal recommendation: {strategy_type} - Take: {should_take_trade}, "
                       f"Confidence: {confidence:.2f} → {calibrated_confidence:.2f}")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error getting signal recommendation: {e}")
            # Return conservative recommendation on error
            return SignalRecommendation(
                should_take_trade=False,
                confidence_adjustment=0.0,
                recommended_position_size=0.01,
                expected_win_rate=0.5,
                expected_pnl_pct=0.0,
                reasoning="Error in ML analysis - conservative approach"
            )
    
    async def get_strategy_insights(self, strategy_type: str, system_type: str) -> Dict[str, Any]:
        """Get insights about a strategy's performance"""
        try:
            await self._ensure_cache_fresh()
            
            query = text("""
            SELECT confidence_range, market_regime, volatility_regime,
                   total_trades, winning_trades, win_rate, avg_pnl_pct,
                   avg_duration_minutes, sharpe_ratio
            FROM strategy_performance_learning
            WHERE strategy_type = :strategy_type AND system_type = :system_type
            ORDER BY total_trades DESC
            """)
            
            with self.db.session_scope() as session:
                result = session.execute(query, {
                    'strategy_type': strategy_type,
                    'system_type': system_type
                })
                
                insights = {
                    'strategy_type': strategy_type,
                    'system_type': system_type,
                    'performance_by_confidence': [],
                    'performance_by_market_regime': [],
                    'overall_stats': {
                        'total_trades': 0,
                        'overall_win_rate': 0.0,
                        'best_confidence_range': None,
                        'best_market_regime': None
                    }
                }
                
                total_trades = 0
                total_wins = 0
                best_win_rate = 0.0
                best_confidence_range = None
                best_market_regime = None
                
                for row in result:
                    perf_data = {
                        'confidence_range': row.confidence_range,
                        'market_regime': row.market_regime,
                        'volatility_regime': row.volatility_regime,
                        'total_trades': row.total_trades,
                        'win_rate': row.win_rate,
                        'avg_pnl_pct': row.avg_pnl_pct,
                        'avg_duration_minutes': row.avg_duration_minutes,
                        'sharpe_ratio': row.sharpe_ratio
                    }
                    
                    insights['performance_by_confidence'].append(perf_data)
                    
                    total_trades += row.total_trades
                    total_wins += row.winning_trades
                    
                    if row.win_rate > best_win_rate and row.total_trades >= 5:
                        best_win_rate = row.win_rate
                        best_confidence_range = row.confidence_range
                        best_market_regime = row.market_regime
                
                insights['overall_stats'] = {
                    'total_trades': total_trades,
                    'overall_win_rate': total_wins / max(total_trades, 1),
                    'best_confidence_range': best_confidence_range,
                    'best_market_regime': best_market_regime,
                    'best_win_rate': best_win_rate
                }
                
                return insights
                
        except Exception as e:
            logger.error(f"Error getting strategy insights: {e}")
            return {'error': str(e)}
    
    async def get_learning_summary(self) -> Dict[str, Any]:
        """Get overall learning summary across all systems"""
        try:
            query = text("""
            SELECT 
                system_type,
                COUNT(*) as total_trades,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as winning_trades,
                AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as win_rate,
                AVG(CAST(pnl_pct AS FLOAT)) as avg_pnl_pct,
                AVG(CAST(duration_minutes AS FLOAT)) as avg_duration_minutes
            FROM ml_training_data
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY system_type
            """)
            
            with self.db.session_scope() as session:
                result = session.execute(query)
                
                summary = {
                    'learning_period_days': 30,
                    'systems': {},
                    'cross_system_insights': {},
                    'last_updated': datetime.now().isoformat()
                }
                
                for row in result:
                    summary['systems'][row.system_type] = {
                        'total_trades': row.total_trades,
                        'winning_trades': row.winning_trades,
                        'win_rate': row.win_rate,
                        'avg_pnl_pct': row.avg_pnl_pct,
                        'avg_duration_minutes': row.avg_duration_minutes
                    }
                
                # Add cross-system insights
                if 'paper_trading' in summary['systems'] and 'profit_scraping' in summary['systems']:
                    paper_win_rate = summary['systems']['paper_trading']['win_rate']
                    real_win_rate = summary['systems']['profit_scraping']['win_rate']
                    
                    summary['cross_system_insights'] = {
                        'paper_vs_real_win_rate_diff': real_win_rate - paper_win_rate,
                        'learning_transfer_effectiveness': min(real_win_rate / max(paper_win_rate, 0.1), 2.0),
                        'recommendation': self._get_cross_system_recommendation(paper_win_rate, real_win_rate)
                    }
                
                return summary
                
        except Exception as e:
            logger.error(f"Error getting learning summary: {e}")
            return {'error': str(e)}
    
    async def _create_ml_tables(self):
        """Create ML learning tables if they don't exist"""
        try:
            # Read and execute the ML tables creation script
            with open('src/database/migrations/create_ml_learning_tables.sql', 'r') as f:
                sql_script = f.read()
            
            with self.db.session_scope() as session:
                session.execute(text(sql_script))
            
            logger.info("✅ ML learning tables created/verified")
            
        except Exception as e:
            logger.error(f"Error creating ML tables: {e}")
            raise
    
    async def _update_strategy_performance(self, trade_outcome: TradeOutcome):
        """Update strategy performance learning"""
        try:
            confidence_range = self._get_confidence_range(trade_outcome.confidence_score)
            
            query = text("""
            INSERT INTO strategy_performance_learning 
            (strategy_type, system_type, confidence_range, market_regime, volatility_regime,
             total_trades, winning_trades, losing_trades, win_rate, avg_pnl_pct, 
             avg_duration_minutes, total_pnl)
            VALUES (:strategy_type, :system_type, :confidence_range, :market_regime, :volatility_regime,
                    1, :winning, :losing, :win_rate, :pnl_pct, :duration, :pnl_pct)
            ON CONFLICT (strategy_type, system_type, confidence_range, market_regime, volatility_regime)
            DO UPDATE SET
                total_trades = strategy_performance_learning.total_trades + 1,
                winning_trades = strategy_performance_learning.winning_trades + :winning,
                losing_trades = strategy_performance_learning.losing_trades + :losing,
                win_rate = (strategy_performance_learning.winning_trades + :winning)::float / 
                          (strategy_performance_learning.total_trades + 1),
                avg_pnl_pct = (strategy_performance_learning.avg_pnl_pct * strategy_performance_learning.total_trades + :pnl_pct) /
                             (strategy_performance_learning.total_trades + 1),
                avg_duration_minutes = (strategy_performance_learning.avg_duration_minutes * strategy_performance_learning.total_trades + :duration) /
                                      (strategy_performance_learning.total_trades + 1),
                total_pnl = strategy_performance_learning.total_pnl + :pnl_pct,
                last_updated = NOW()
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'strategy_type': trade_outcome.strategy_type,
                    'system_type': trade_outcome.system_type,
                    'confidence_range': confidence_range,
                    'market_regime': trade_outcome.market_regime,
                    'volatility_regime': trade_outcome.volatility_regime,
                    'winning': 1 if trade_outcome.success else 0,
                    'losing': 0 if trade_outcome.success else 1,
                    'win_rate': 1.0 if trade_outcome.success else 0.0,
                    'pnl_pct': trade_outcome.pnl_pct or 0.0,
                    'duration': trade_outcome.duration_minutes or 0
                })
            
        except Exception as e:
            logger.error(f"Error updating strategy performance: {e}")
    
    async def _update_signal_quality(self, trade_outcome: TradeOutcome):
        """Update signal quality learning"""
        try:
            confidence_bucket = round(trade_outcome.confidence_score, 1)
            
            query = text("""
            INSERT INTO signal_quality_learning 
            (signal_type, confidence_bucket, predicted_success_rate, actual_success_rate, sample_size)
            VALUES (:signal_type, :confidence_bucket, :confidence_bucket, :success_rate, 1)
            ON CONFLICT (signal_type, confidence_bucket)
            DO UPDATE SET
                actual_success_rate = (signal_quality_learning.actual_success_rate * signal_quality_learning.sample_size + :success_rate) /
                                     (signal_quality_learning.sample_size + 1),
                sample_size = signal_quality_learning.sample_size + 1,
                calibration_score = ABS(signal_quality_learning.predicted_success_rate - 
                                       ((signal_quality_learning.actual_success_rate * signal_quality_learning.sample_size + :success_rate) /
                                        (signal_quality_learning.sample_size + 1))),
                last_updated = NOW()
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'signal_type': trade_outcome.strategy_type,
                    'confidence_bucket': confidence_bucket,
                    'success_rate': 1.0 if trade_outcome.success else 0.0
                })
            
        except Exception as e:
            logger.error(f"Error updating signal quality: {e}")
    
    async def _update_market_regime_learning(self, trade_outcome: TradeOutcome):
        """Update market regime learning"""
        try:
            query = text("""
            INSERT INTO market_regime_learning 
            (market_regime, volatility_regime, total_trades_in_regime, avg_trade_duration_minutes)
            VALUES (:market_regime, :volatility_regime, 1, :duration)
            ON CONFLICT (market_regime, volatility_regime)
            DO UPDATE SET
                total_trades_in_regime = market_regime_learning.total_trades_in_regime + 1,
                avg_trade_duration_minutes = (market_regime_learning.avg_trade_duration_minutes * market_regime_learning.total_trades_in_regime + :duration) /
                                            (market_regime_learning.total_trades_in_regime + 1),
                last_updated = NOW()
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'market_regime': trade_outcome.market_regime,
                    'volatility_regime': trade_outcome.volatility_regime,
                    'duration': trade_outcome.duration_minutes or 0
                })
            
        except Exception as e:
            logger.error(f"Error updating market regime learning: {e}")
    
    async def _get_strategy_performance(self, strategy_type: str, confidence: float, 
                                      market_regime: str, volatility_regime: str) -> Dict[str, Any]:
        """Get strategy performance for similar conditions"""
        try:
            confidence_range = self._get_confidence_range(confidence)
            
            query = text("""
            SELECT win_rate, avg_pnl_pct, avg_duration_minutes, total_trades, sharpe_ratio
            FROM strategy_performance_learning
            WHERE strategy_type = :strategy_type 
            AND confidence_range = :confidence_range
            AND (market_regime = :market_regime OR market_regime IS NULL)
            AND (volatility_regime = :volatility_regime OR volatility_regime IS NULL)
            ORDER BY total_trades DESC
            LIMIT 1
            """)
            
            with self.db.session_scope() as session:
                result = session.execute(query, {
                    'strategy_type': strategy_type,
                    'confidence_range': confidence_range,
                    'market_regime': market_regime,
                    'volatility_regime': volatility_regime
                }).fetchone()
                
                if result:
                    return {
                        'win_rate': result.win_rate,
                        'avg_pnl_pct': result.avg_pnl_pct,
                        'avg_duration_minutes': result.avg_duration_minutes,
                        'total_trades': result.total_trades,
                        'sharpe_ratio': result.sharpe_ratio or 0.0
                    }
                else:
                    # Return defaults if no historical data
                    return {
                        'win_rate': 0.5,
                        'avg_pnl_pct': 0.0,
                        'avg_duration_minutes': 60.0,
                        'total_trades': 0,
                        'sharpe_ratio': 0.0
                    }
                    
        except Exception as e:
            logger.error(f"Error getting strategy performance: {e}")
            return {
                'win_rate': 0.5,
                'avg_pnl_pct': 0.0,
                'avg_duration_minutes': 60.0,
                'total_trades': 0,
                'sharpe_ratio': 0.0
            }
    
    async def _calibrate_confidence(self, strategy_type: str, confidence: float) -> float:
        """Calibrate confidence score based on historical accuracy"""
        try:
            confidence_bucket = round(confidence, 1)
            
            query = text("""
            SELECT actual_success_rate, predicted_success_rate, sample_size
            FROM signal_quality_learning
            WHERE signal_type = :strategy_type AND confidence_bucket = :confidence_bucket
            """)
            
            with self.db.session_scope() as session:
                result = session.execute(query, {
                    'strategy_type': strategy_type,
                    'confidence_bucket': confidence_bucket
                }).fetchone()
                
                if result and result.sample_size >= 10:
                    # Adjust confidence based on historical accuracy
                    calibration_factor = result.actual_success_rate / max(result.predicted_success_rate, 0.1)
                    calibrated = confidence * calibration_factor
                    return max(0.1, min(0.95, calibrated))
                else:
                    # Not enough data, return original confidence
                    return confidence
                    
        except Exception as e:
            logger.error(f"Error calibrating confidence: {e}")
            return confidence
    
    async def _get_optimal_position_size(self, confidence: float, market_regime: str, 
                                       volatility_regime: str) -> float:
        """Get optimal position size based on confidence and market conditions"""
        try:
            # Base position size on confidence
            base_size = confidence * 0.02  # Max 2% at 100% confidence
            
            # Adjust for market regime (simplified)
            if market_regime == 'trending':
                base_size *= 1.2
            elif market_regime == 'ranging':
                base_size *= 0.8
            
            # Adjust for volatility
            if volatility_regime == 'high':
                base_size *= 0.7
            elif volatility_regime == 'low':
                base_size *= 1.1
            
            return max(0.005, min(0.05, base_size))  # Between 0.5% and 5%
            
        except Exception as e:
            logger.error(f"Error getting optimal position size: {e}")
            return 0.01
    
    async def _should_take_trade(self, strategy_type: str, confidence: float, 
                               market_regime: str, performance: Dict[str, Any]) -> bool:
        """Determine if we should take the trade based on ML insights"""
        try:
            # Minimum confidence threshold
            if confidence < 0.5:
                return False
            
            # Check if we have enough historical data
            if performance['total_trades'] >= 10:
                # Use historical win rate
                if performance['win_rate'] < 0.4:  # Less than 40% win rate
                    return False
                
                # Check if expected return is positive
                if performance['avg_pnl_pct'] <= 0:
                    return False
            
            # Check market regime compatibility
            # This would be more sophisticated in a full implementation
            
            return True
            
        except Exception as e:
            logger.error(f"Error determining if should take trade: {e}")
            return False
    
    def _generate_reasoning(self, performance: Dict[str, Any], calibrated_confidence: float, 
                          original_confidence: float, should_take_trade: bool) -> str:
        """Generate human-readable reasoning for the recommendation"""
        try:
            reasoning_parts = []
            
            if performance['total_trades'] >= 10:
                reasoning_parts.append(f"Historical win rate: {performance['win_rate']:.1%}")
                reasoning_parts.append(f"Average P&L: {performance['avg_pnl_pct']:.2%}")
            else:
                reasoning_parts.append("Limited historical data")
            
            if abs(calibrated_confidence - original_confidence) > 0.05:
                reasoning_parts.append(f"Confidence adjusted: {original_confidence:.2f} → {calibrated_confidence:.2f}")
            
            if should_take_trade:
                reasoning_parts.append("✅ Recommended based on ML analysis")
            else:
                reasoning_parts.append("❌ Not recommended based on ML analysis")
            
            return " | ".join(reasoning_parts)
            
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return "ML analysis completed"
    
    def _get_confidence_range(self, confidence: float) -> str:
        """Convert confidence score to range bucket"""
        if confidence < 0.5:
            return "0.0-0.5"
        elif confidence < 0.6:
            return "0.5-0.6"
        elif confidence < 0.7:
            return "0.6-0.7"
        elif confidence < 0.8:
            return "0.7-0.8"
        elif confidence < 0.9:
            return "0.8-0.9"
        else:
            return "0.9-1.0"
    
    def _get_cross_system_recommendation(self, paper_win_rate: float, real_win_rate: float) -> str:
        """Get recommendation based on cross-system performance"""
        if real_win_rate > paper_win_rate + 0.1:
            return "Real trading outperforming paper trading - consider increasing position sizes"
        elif paper_win_rate > real_win_rate + 0.1:
            return "Paper trading outperforming real trading - review real trading execution"
        else:
            return "Paper and real trading performance aligned - system working well"
    
    async def _refresh_cache(self):
        """Refresh the learning cache"""
        try:
            self.cache_expiry = datetime.now() + timedelta(minutes=self.cache_duration_minutes)
            logger.info("🔄 ML learning cache refreshed")
            
        except Exception as e:
            logger.error(f"Error refreshing cache: {e}")
    
    async def _ensure_cache_fresh(self):
        """Ensure cache is fresh"""
        if datetime.now() > self.cache_expiry:
            await self._refresh_cache()

# Global ML learning service instance
ml_learning_service: Optional[MLLearningService] = None

async def get_ml_learning_service() -> MLLearningService:
    """Get or create the global ML learning service instance"""
    global ml_learning_service
    
    if ml_learning_service is None:
        ml_learning_service = MLLearningService()
        await ml_learning_service.initialize()
    
    return ml_learning_service
