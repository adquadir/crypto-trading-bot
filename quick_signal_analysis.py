#!/usr/bin/env python3
"""
Quick analysis of signal generation - checking if we're actually getting 3% moves
and if take profits are realistically achievable
"""

import asyncio
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def quick_signal_test():
    """Quick test on just a few popular symbols."""
    try:
        logger.info("🎯 Quick Signal Analysis - 3% Move Validation")
        
        # Initialize components
        exchange_client = ExchangeClient()
        strategy_manager = StrategyManager(exchange_client)
        
        risk_config = {
            'risk': {
                'max_drawdown': 0.2,
                'max_leverage': 5.0,
                'position_size_limit': 1000.0,
                'daily_loss_limit': 100.0,
                'initial_balance': 10000.0
            },
            'trading': {
                'max_volatility': 0.5,
                'max_spread': 0.01
            }
        }
        risk_manager = RiskManager(risk_config)
        
        opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
        await opportunity_manager.initialize()
        
        # Set current time for signals
        import time
        opportunity_manager.current_time = time.time()
        
        # Test with just 5 popular symbols for speed
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']
        
        logger.info(f"📊 Testing {len(test_symbols)} symbols for 3% precision moves...")
        
        all_signals = []
        
        for symbol in test_symbols:
            try:
                logger.info(f"🔍 Testing {symbol}...")
                
                # Get market data for this symbol
                market_data = await opportunity_manager._get_market_data_for_signal_stable(symbol)
                if not market_data:
                    logger.warning(f"❌ No market data for {symbol}")
                    continue
                
                # Generate signal
                signal = opportunity_manager._analyze_market_and_generate_signal_balanced(
                    symbol, market_data, opportunity_manager.current_time
                )
                
                if signal:
                    all_signals.append(signal)
                    
                    # Calculate move percentage
                    entry = signal['entry_price']
                    tp = signal['take_profit']
                    sl = signal['stop_loss']
                    move_pct = abs(tp - entry) / entry * 100
                    
                    logger.info(f"✅ {symbol} {signal['direction']} Signal Generated:")
                    logger.info(f"   Entry: ${entry:.6f}")
                    logger.info(f"   Take Profit: ${tp:.6f}")
                    logger.info(f"   Stop Loss: ${sl:.6f}")
                    logger.info(f"   🎯 Move: {move_pct:.2f}%")
                    logger.info(f"   Confidence: {signal['confidence']:.2f}")
                    logger.info(f"   R:R: {signal.get('risk_reward', 0):.2f}")
                    
                    # Check if it's in the 3% precision range
                    if 2.5 <= move_pct <= 3.5:
                        logger.info(f"   ✅ PERFECT 3% PRECISION!")
                    elif 2.0 <= move_pct <= 4.0:
                        logger.info(f"   🟡 Good precision range")
                    else:
                        logger.info(f"   ❌ Outside precision range")
                    
                    # Check validation
                    validated = signal.get('validation_applied', False)
                    tradable = signal.get('tradable', True)
                    logger.info(f"   Validated: {validated}, Tradable: {tradable}")
                    
                    if not tradable:
                        reason = signal.get('rejection_reason', 'Unknown')
                        logger.info(f"   ❌ Rejection: {reason}")
                
                else:
                    logger.info(f"❌ No signal generated for {symbol}")
                    
            except Exception as e:
                logger.error(f"❌ Error testing {symbol}: {e}")
        
        # Summary analysis
        logger.info(f"\n📊 SUMMARY ANALYSIS:")
        logger.info(f"Symbols tested: {len(test_symbols)}")
        logger.info(f"Signals generated: {len(all_signals)}")
        
        if all_signals:
            moves = [abs(s['take_profit'] - s['entry_price']) / s['entry_price'] * 100 for s in all_signals]
            confidences = [s['confidence'] for s in all_signals]
            
            avg_move = sum(moves) / len(moves)
            avg_confidence = sum(confidences) / len(confidences)
            
            precision_signals = [m for m in moves if 2.5 <= m <= 3.5]
            good_signals = [m for m in moves if 2.0 <= m <= 4.0]
            
            logger.info(f"Average move: {avg_move:.2f}%")
            logger.info(f"Average confidence: {avg_confidence:.2f}")
            logger.info(f"Perfect 3% precision: {len(precision_signals)}/{len(moves)} ({len(precision_signals)/len(moves)*100:.1f}%)")
            logger.info(f"Good precision (2-4%): {len(good_signals)}/{len(moves)} ({len(good_signals)/len(moves)*100:.1f}%)")
            
            # Show move distribution
            logger.info(f"Move distribution: {[f'{m:.2f}%' for m in moves]}")
            
            # Check validation results
            validated_count = sum(1 for s in all_signals if s.get('validation_applied', False))
            tradable_count = sum(1 for s in all_signals if s.get('tradable', True))
            
            logger.info(f"Validated signals: {validated_count}/{len(all_signals)}")
            logger.info(f"Tradable signals: {tradable_count}/{len(all_signals)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function."""
    logger.info("🚀 Starting Quick Signal Analysis")
    
    success = await quick_signal_test()
    
    if success:
        logger.info("✅ Analysis completed!")
        return 0
    else:
        logger.error("❌ Analysis failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 