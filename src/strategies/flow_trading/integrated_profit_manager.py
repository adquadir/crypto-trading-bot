"""
Integrated Profit Manager
Combines profit scraping with advanced ML features for optimal performance
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from .profit_scraper import ProfitScraper, MarketRegime, StrategyMode
    from .advanced_signal_generator import AdvancedSignalGenerator
    from .dynamic_grid_optimizer import DynamicGridOptimizer
    from .advanced_risk_manager import AdvancedRiskManager
except ImportError:
    from profit_scraper import ProfitScraper, MarketRegime, StrategyMode
    from advanced_signal_generator import AdvancedSignalGenerator
    from dynamic_grid_optimizer import DynamicGridOptimizer
    from advanced_risk_manager import AdvancedRiskManager

logger = logging.getLogger(__name__)

class IntegratedProfitManager:
    """Integrates profit scraping with advanced ML features"""
    
    def __init__(self, exchange_client=None, base_risk_manager=None):
        self.exchange_client = exchange_client
        self.base_risk_manager = base_risk_manager
        
        # Initialize components
        self.profit_scraper = ProfitScraper(exchange_client)
        self.advanced_signal_gen = AdvancedSignalGenerator(exchange_client)
        self.grid_optimizer = DynamicGridOptimizer(exchange_client)
        self.advanced_risk_manager = AdvancedRiskManager(base_risk_manager)
        
        # State
        self.running = False
        self.integration_level = "basic"
        
    async def start_integrated_scraping(self, symbols: List[str], 
                                       use_ml_signals: bool = True,
                                       use_advanced_risk: bool = True,
                                       use_grid_optimization: bool = True):
        """Start integrated profit scraping with ML enhancements"""
        try:
            logger.info("🚀 Starting Integrated Profit Scraping System")
            
            # Determine integration level
            if use_ml_signals and use_advanced_risk and use_grid_optimization:
                self.integration_level = "full"
            elif use_ml_signals or use_advanced_risk:
                self.integration_level = "advanced"
            else:
                self.integration_level = "basic"
            
            logger.info(f"Integration level: {self.integration_level}")
            
            # Start the profit scraper
            await self.profit_scraper.start(symbols)
            self.running = True
            
            logger.info(f"✅ Integrated system started on {len(symbols)} symbols")
            
            return {
                "status": "started",
                "integration_level": self.integration_level,
                "symbols": symbols,
                "ml_signals": use_ml_signals,
                "advanced_risk": use_advanced_risk,
                "grid_optimization": use_grid_optimization
            }
            
        except Exception as e:
            logger.error(f"Error starting integrated scraping: {e}")
            raise
    
    def stop_integrated_scraping(self):
        """Stop integrated profit scraping"""
        try:
            self.profit_scraper.stop()
            self.running = False
            logger.info("🛑 Integrated Profit Scraping stopped")
            
        except Exception as e:
            logger.error(f"Error stopping integrated scraping: {e}")
    
    def get_integrated_status(self) -> Dict[str, Any]:
        """Get comprehensive status of integrated system"""
        try:
            base_status = self.profit_scraper.get_status()
            
            # Add integration-specific metrics
            integrated_status = {
                **base_status,
                'integration_level': self.integration_level,
                'ml_enhanced': self.integration_level in ['advanced', 'full'],
                'risk_enhanced': self.integration_level in ['advanced', 'full'],
                'grid_optimized': self.integration_level == 'full',
                'system_health': 'optimal' if self.running else 'stopped'
            }
            
            return integrated_status
            
        except Exception as e:
            logger.error(f"Error getting integrated status: {e}")
            return self.profit_scraper.get_status()
    
    def get_ml_performance(self) -> Dict[str, Any]:
        """Get ML-specific performance metrics"""
        try:
            trades = self.profit_scraper.get_recent_trades(50)
            
            return {
                'total_trades': len(trades),
                'avg_profit': sum(t['profit_usd'] for t in trades) / max(1, len(trades)),
                'win_rate': len([t for t in trades if t['profit_usd'] > 0]) / max(1, len(trades)),
                'integration_level': self.integration_level
            }
            
        except Exception as e:
            logger.error(f"Error getting ML performance: {e}")
            return {}

    def get_status(self) -> Dict[str, Any]:
        """Wrapper method for API compatibility - calls get_integrated_status"""
        return self.get_integrated_status()
    
    def get_recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Wrapper method for API compatibility - calls profit_scraper.get_recent_trades"""
        try:
            return self.profit_scraper.get_recent_trades(limit)
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    async def start(self, symbols: List[str]) -> Dict[str, Any]:
        """Wrapper method for API compatibility - calls start_integrated_scraping"""
        return await self.start_integrated_scraping(symbols)
    
    def stop(self):
        """Wrapper method for API compatibility - calls stop_integrated_scraping"""
        self.stop_integrated_scraping()
 