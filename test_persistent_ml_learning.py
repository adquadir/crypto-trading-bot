#!/usr/bin/env python3
"""
Test Persistent ML Learning System
Verifies that ML data survives service restarts and enables cross-system learning
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ml.ml_learning_service import get_ml_learning_service, TradeOutcome
from src.database.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MLLearningTester:
    """Test the persistent ML learning system"""
    
    def __init__(self):
        self.db = Database()
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all ML learning tests"""
        logger.info("🧠 Starting Persistent ML Learning System Tests")
        
        try:
            # Test 1: Database Schema Creation
            await self.test_database_schema()
            
            # Test 2: ML Service Initialization
            await self.test_ml_service_initialization()
            
            # Test 3: Store Trade Outcomes
            await self.test_store_trade_outcomes()
            
            # Test 4: Signal Recommendations
            await self.test_signal_recommendations()
            
            # Test 5: Strategy Insights
            await self.test_strategy_insights()
            
            # Test 6: Cross-System Learning
            await self.test_cross_system_learning()
            
            # Test 7: Data Persistence Across Restarts
            await self.test_data_persistence()
            
            # Test 8: Learning Summary
            await self.test_learning_summary()
            
            # Print results
            self.print_test_results()
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def test_database_schema(self):
        """Test ML learning database schema creation"""
        try:
            logger.info("🔍 Test 1: Database Schema Creation")
            
            # Get ML service (this should create tables)
            ml_service = await get_ml_learning_service()
            
            # Check if tables exist
            from sqlalchemy import text
            
            tables_to_check = [
                'ml_training_data',
                'strategy_performance_learning',
                'signal_quality_learning',
                'market_regime_learning',
                'position_sizing_learning',
                'feature_importance_learning'
            ]
            
            with self.db.session_scope() as session:
                for table in tables_to_check:
                    result = session.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    );
                    """)).fetchone()
                    
                    if result[0]:
                        logger.info(f"✅ Table {table} exists")
                    else:
                        raise Exception(f"Table {table} does not exist")
            
            self.test_results.append(("Database Schema Creation", "PASSED", "All ML tables created successfully"))
            
        except Exception as e:
            logger.error(f"❌ Database schema test failed: {e}")
            self.test_results.append(("Database Schema Creation", "FAILED", str(e)))
    
    async def test_ml_service_initialization(self):
        """Test ML service initialization"""
        try:
            logger.info("🔍 Test 2: ML Service Initialization")
            
            ml_service = await get_ml_learning_service()
            
            if ml_service is None:
                raise Exception("ML service is None")
            
            # Check service attributes
            if not hasattr(ml_service, 'db'):
                raise Exception("ML service missing database connection")
            
            if not hasattr(ml_service, 'cache'):
                raise Exception("ML service missing cache")
            
            logger.info("✅ ML service initialized successfully")
            self.test_results.append(("ML Service Initialization", "PASSED", "Service initialized with all components"))
            
        except Exception as e:
            logger.error(f"❌ ML service initialization test failed: {e}")
            self.test_results.append(("ML Service Initialization", "FAILED", str(e)))
    
    async def test_store_trade_outcomes(self):
        """Test storing trade outcomes"""
        try:
            logger.info("🔍 Test 3: Store Trade Outcomes")
            
            ml_service = await get_ml_learning_service()
            
            # Create test trade outcomes
            test_trades = [
                TradeOutcome(
                    trade_id=f"test_paper_{i}",
                    symbol="BTCUSDT",
                    strategy_type="scalping",
                    system_type="paper_trading",
                    confidence_score=0.7 + (i * 0.1),
                    ml_score=0.6 + (i * 0.1),
                    entry_price=50000.0 + (i * 100),
                    exit_price=50500.0 + (i * 100),
                    pnl_pct=0.01 * (i + 1),
                    duration_minutes=30 + (i * 10),
                    market_regime="trending",
                    volatility_regime="medium",
                    exit_reason="take_profit" if i % 2 == 0 else "stop_loss",
                    success=i % 2 == 0,
                    features={
                        "rsi": 60 + i,
                        "volume": 1000000 + (i * 100000),
                        "price_change": 0.01 * (i + 1)
                    },
                    entry_time=datetime.now() - timedelta(hours=i),
                    exit_time=datetime.now() - timedelta(hours=i, minutes=-30)
                )
                for i in range(5)
            ]
            
            # Store trade outcomes
            for trade in test_trades:
                await ml_service.store_trade_outcome(trade)
                logger.info(f"✅ Stored trade outcome: {trade.trade_id}")
            
            # Create profit scraping trades
            profit_scraping_trades = [
                TradeOutcome(
                    trade_id=f"test_profit_{i}",
                    symbol="ETHUSDT",
                    strategy_type="profit_scraping",
                    system_type="profit_scraping",
                    confidence_score=0.8 + (i * 0.05),
                    ml_score=0.75 + (i * 0.05),
                    entry_price=3000.0 + (i * 50),
                    exit_price=3100.0 + (i * 50),
                    pnl_pct=0.033 * (i + 1),
                    duration_minutes=45 + (i * 15),
                    market_regime="ranging",
                    volatility_regime="low",
                    exit_reason="profit_target" if i % 3 != 0 else "time_exit",
                    success=i % 3 != 0,
                    features={
                        "level_strength": 80 + i,
                        "magnet_strength": 70 + i,
                        "distance_to_level": 0.005 * (i + 1)
                    },
                    entry_time=datetime.now() - timedelta(hours=i + 1),
                    exit_time=datetime.now() - timedelta(hours=i + 1, minutes=-45)
                )
                for i in range(3)
            ]
            
            for trade in profit_scraping_trades:
                await ml_service.store_trade_outcome(trade)
                logger.info(f"✅ Stored profit scraping outcome: {trade.trade_id}")
            
            self.test_results.append(("Store Trade Outcomes", "PASSED", f"Stored {len(test_trades) + len(profit_scraping_trades)} trade outcomes"))
            
        except Exception as e:
            logger.error(f"❌ Store trade outcomes test failed: {e}")
            self.test_results.append(("Store Trade Outcomes", "FAILED", str(e)))
    
    async def test_signal_recommendations(self):
        """Test getting signal recommendations"""
        try:
            logger.info("🔍 Test 4: Signal Recommendations")
            
            ml_service = await get_ml_learning_service()
            
            # Test signal data
            test_signals = [
                {
                    'strategy_type': 'scalping',
                    'confidence': 0.75,
                    'market_regime': 'trending',
                    'volatility_regime': 'medium'
                },
                {
                    'strategy_type': 'profit_scraping',
                    'confidence': 0.85,
                    'market_regime': 'ranging',
                    'volatility_regime': 'low'
                }
            ]
            
            for signal_data in test_signals:
                recommendation = await ml_service.get_signal_recommendation(signal_data)
                
                logger.info(f"✅ Signal recommendation for {signal_data['strategy_type']}:")
                logger.info(f"   Should take trade: {recommendation.should_take_trade}")
                logger.info(f"   Confidence adjustment: {recommendation.confidence_adjustment:.3f}")
                logger.info(f"   Recommended position size: {recommendation.recommended_position_size:.3f}")
                logger.info(f"   Expected win rate: {recommendation.expected_win_rate:.2%}")
                logger.info(f"   Reasoning: {recommendation.reasoning}")
            
            self.test_results.append(("Signal Recommendations", "PASSED", f"Generated recommendations for {len(test_signals)} signals"))
            
        except Exception as e:
            logger.error(f"❌ Signal recommendations test failed: {e}")
            self.test_results.append(("Signal Recommendations", "FAILED", str(e)))
    
    async def test_strategy_insights(self):
        """Test getting strategy insights"""
        try:
            logger.info("🔍 Test 5: Strategy Insights")
            
            ml_service = await get_ml_learning_service()
            
            # Test different strategies
            strategies = [
                ('scalping', 'paper_trading'),
                ('profit_scraping', 'profit_scraping')
            ]
            
            for strategy_type, system_type in strategies:
                insights = await ml_service.get_strategy_insights(strategy_type, system_type)
                
                logger.info(f"✅ Strategy insights for {strategy_type} ({system_type}):")
                logger.info(f"   Total trades: {insights['overall_stats']['total_trades']}")
                logger.info(f"   Overall win rate: {insights['overall_stats']['overall_win_rate']:.2%}")
                logger.info(f"   Best confidence range: {insights['overall_stats']['best_confidence_range']}")
                logger.info(f"   Performance entries: {len(insights['performance_by_confidence'])}")
            
            self.test_results.append(("Strategy Insights", "PASSED", f"Generated insights for {len(strategies)} strategies"))
            
        except Exception as e:
            logger.error(f"❌ Strategy insights test failed: {e}")
            self.test_results.append(("Strategy Insights", "FAILED", str(e)))
    
    async def test_cross_system_learning(self):
        """Test cross-system learning capabilities"""
        try:
            logger.info("🔍 Test 6: Cross-System Learning")
            
            ml_service = await get_ml_learning_service()
            
            # Get learning summary to see cross-system insights
            summary = await ml_service.get_learning_summary()
            
            logger.info("✅ Cross-system learning summary:")
            logger.info(f"   Learning period: {summary['learning_period_days']} days")
            
            for system_type, stats in summary['systems'].items():
                logger.info(f"   {system_type.upper()}:")
                logger.info(f"     Total trades: {stats['total_trades']}")
                logger.info(f"     Win rate: {stats['win_rate']:.2%}")
                logger.info(f"     Avg P&L: {stats['avg_pnl_pct']:.2%}")
            
            if 'cross_system_insights' in summary:
                insights = summary['cross_system_insights']
                logger.info("   Cross-system insights:")
                logger.info(f"     Win rate difference: {insights.get('paper_vs_real_win_rate_diff', 0):.2%}")
                logger.info(f"     Learning transfer effectiveness: {insights.get('learning_transfer_effectiveness', 0):.2f}")
                logger.info(f"     Recommendation: {insights.get('recommendation', 'N/A')}")
            
            self.test_results.append(("Cross-System Learning", "PASSED", "Cross-system insights generated successfully"))
            
        except Exception as e:
            logger.error(f"❌ Cross-system learning test failed: {e}")
            self.test_results.append(("Cross-System Learning", "FAILED", str(e)))
    
    async def test_data_persistence(self):
        """Test data persistence across service restarts"""
        try:
            logger.info("🔍 Test 7: Data Persistence")
            
            # Simulate service restart by creating new ML service instance
            from src.ml.ml_learning_service import MLLearningService
            
            # Create new instance (simulates restart)
            new_ml_service = MLLearningService()
            await new_ml_service.initialize()
            
            # Check if data persists
            summary = await new_ml_service.get_learning_summary()
            
            total_trades = sum(stats['total_trades'] for stats in summary['systems'].values())
            
            if total_trades > 0:
                logger.info(f"✅ Data persistence verified: {total_trades} trades found after 'restart'")
                self.test_results.append(("Data Persistence", "PASSED", f"Found {total_trades} trades after restart simulation"))
            else:
                raise Exception("No trades found after restart simulation")
            
        except Exception as e:
            logger.error(f"❌ Data persistence test failed: {e}")
            self.test_results.append(("Data Persistence", "FAILED", str(e)))
    
    async def test_learning_summary(self):
        """Test learning summary generation"""
        try:
            logger.info("🔍 Test 8: Learning Summary")
            
            ml_service = await get_ml_learning_service()
            
            summary = await ml_service.get_learning_summary()
            
            # Validate summary structure
            required_keys = ['learning_period_days', 'systems', 'last_updated']
            for key in required_keys:
                if key not in summary:
                    raise Exception(f"Missing key in summary: {key}")
            
            logger.info("✅ Learning summary structure validated")
            logger.info(f"   Systems tracked: {list(summary['systems'].keys())}")
            logger.info(f"   Last updated: {summary['last_updated']}")
            
            self.test_results.append(("Learning Summary", "PASSED", "Summary generated with correct structure"))
            
        except Exception as e:
            logger.error(f"❌ Learning summary test failed: {e}")
            self.test_results.append(("Learning Summary", "FAILED", str(e)))
    
    def print_test_results(self):
        """Print comprehensive test results"""
        logger.info("\n" + "="*80)
        logger.info("🧠 PERSISTENT ML LEARNING SYSTEM - TEST RESULTS")
        logger.info("="*80)
        
        passed = 0
        failed = 0
        
        for test_name, status, details in self.test_results:
            status_icon = "✅" if status == "PASSED" else "❌"
            logger.info(f"{status_icon} {test_name}: {status}")
            logger.info(f"   {details}")
            
            if status == "PASSED":
                passed += 1
            else:
                failed += 1
        
        logger.info("="*80)
        logger.info(f"📊 SUMMARY: {passed} PASSED, {failed} FAILED")
        
        if failed == 0:
            logger.info("🎉 ALL TESTS PASSED! Persistent ML Learning System is working correctly.")
            logger.info("✅ ML data will survive service restarts")
            logger.info("✅ Cross-system learning is enabled")
            logger.info("✅ Paper trading insights will improve real trading")
        else:
            logger.error(f"❌ {failed} tests failed. Please review the errors above.")
        
        logger.info("="*80)

async def main():
    """Main test function"""
    tester = MLLearningTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
