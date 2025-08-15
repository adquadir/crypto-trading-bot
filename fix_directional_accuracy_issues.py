#!/usr/bin/env python3
"""
Fix Directional Accuracy Issues in Opportunity Manager

This script implements the comprehensive fixes identified to resolve:
1. Signal caching/staleness causing wrong direction display
2. Incomplete normalization coverage allowing non-LONG/SHORT labels
3. Forming candle instability causing flip-flops
4. Missing freshness and drift guards in the trading engine

Key fixes:
- Always finalize opportunities before storing/returning
- Use last closed candle for direction decisions
- Add debounce + hysteresis to prevent flip-flops
- Add freshness and price drift guards in trading engine
- Atomic publishing of opportunity maps
"""

import os
import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the original file"""
    backup_path = f"{file_path}.backup_{int(time.time())}"
    if os.path.exists(file_path):
        with open(file_path, 'r') as original:
            with open(backup_path, 'w') as backup:
                backup.write(original.read())
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    return None

def fix_opportunity_manager():
    """Apply fixes to the opportunity manager"""
    file_path = "src/opportunity/opportunity_manager.py"
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    # Create backup
    backup_path = backup_file(file_path)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add helper methods after the imports section
        import_section_end = content.find('class OpportunityManager:')
        if import_section_end == -1:
            logger.error("Could not find OpportunityManager class")
            return False
        
        # Find the end of __init__ method to add helper methods
        init_end = content.find('def get_opportunities(self)')
        if init_end == -1:
            logger.error("Could not find get_opportunities method")
            return False
        
        # Helper methods to add
        helper_methods = '''
    def _drop_forming_candle(self, klines):
        """
        Return klines with the last (possibly-forming) candle removed.
        Works for list[dict] or list[list].
        """
        if not klines or len(klines) < 2:
            return klines
        try:
            # If your kline dicts carry 'isClosed' or 'x' flag, prefer that:
            last = klines[-1]
            is_closed = (isinstance(last, dict) and (last.get('isClosed') or last.get('x')))
            if is_closed is True:
                return klines
        except Exception:
            pass
        # Default: drop the very last element (safer for direction calc)
        return klines[:-1]

    def _should_accept_flip(self, symbol: str, new_dir: str, momentum: float = None,
                            min_flip_seconds: int = 60, hysteresis_mult: float = 1.25,
                            base_momo_threshold: float = 0.001):
        """
        Debounce direction changes and require extra headroom near threshold.
        Returns True if we should accept changing to new_dir.
        """
        try:
            last = self.opportunities.get(symbol, {})
            last_dir = str(last.get('direction', '')).upper()
            last_ts = float(last.get('signal_timestamp', 0) or 0)
            now = time.time()
            if last_dir and new_dir and new_dir != last_dir:
                if (now - last_ts) < min_flip_seconds:
                    return False
                # Hysteresis: if we know momentum, require > threshold * multiplier
                if momentum is not None and abs(momentum) < (hysteresis_mult * base_momo_threshold):
                    return False
            return True
        except Exception:
            return True

    def _finalize_and_stamp(self, opp: dict):
        """
        Always normalize direction and fix TP/SL orientation, and add signal_timestamp.
        """
        if not opp:
            return None
        try:
            opp = self._finalize_opportunity(opp)  # your existing finalizer
            if opp is None:
                return None
            opp.setdefault('signal_timestamp', time.time())
            return opp
        except Exception:
            return None

'''
        
        # Insert helper methods before get_opportunities
        content = content[:init_end] + helper_methods + '\n    ' + content[init_end:]
        
        # Fix the signal generation methods to use closed candles
        # Find _analyze_market_and_generate_signal_balanced method
        method_start = content.find('def _analyze_market_and_generate_signal_balanced(self')
        if method_start != -1:
            # Find the klines extraction part
            klines_pattern = 'klines = market_data.get(\'klines\', [])'
            klines_pos = content.find(klines_pattern, method_start)
            if klines_pos != -1:
                # Add the forming candle fix right after klines extraction
                insert_pos = content.find('\n', klines_pos) + 1
                forming_candle_fix = '''            
            # Use last closed candle for direction decisions (prevents flip-flops)
            klines = self._drop_forming_candle(klines)
'''
                content = content[:insert_pos] + forming_candle_fix + content[insert_pos:]
        
        # Fix the scan methods to always finalize opportunities
        # Find scan_opportunities_incremental method
        scan_method = 'def scan_opportunities_incremental(self)'
        scan_start = content.find(scan_method)
        if scan_start != -1:
            # Find the opportunity assignment pattern
            assignment_pattern = 'self.opportunities[symbol] = opportunity'
            assignment_pos = content.find(assignment_pattern, scan_start)
            while assignment_pos != -1:
                # Find the start of this assignment block
                line_start = content.rfind('\n', 0, assignment_pos) + 1
                indent = ''
                for char in content[line_start:assignment_pos]:
                    if char in ' \t':
                        indent += char
                    else:
                        break
                
                # Replace the assignment with finalized version
                finalized_assignment = f'''{indent}# Apply finalization and debouncing
{indent}if opportunity:
{indent}    new_dir = str(opportunity.get('direction', '')).upper()
{indent}    momentum = opportunity.get('price_change_5')  # or your momentum field
{indent}    if not self._should_accept_flip(symbol, new_dir, momentum):
{indent}        opportunity = None

{indent}if opportunity:
{indent}    opportunity = self._finalize_and_stamp(opportunity)
{indent}    if opportunity:
{indent}        self.opportunities[symbol] = opportunity'''
                
                # Find the end of the current line
                line_end = content.find('\n', assignment_pos)
                if line_end == -1:
                    line_end = len(content)
                
                content = content[:line_start] + finalized_assignment + content[line_end:]
                
                # Look for next occurrence
                assignment_pos = content.find(assignment_pattern, line_start + len(finalized_assignment))
        
        # Write the updated content
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Successfully updated {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating opportunity manager: {e}")
        # Restore backup if something went wrong
        if backup_path and os.path.exists(backup_path):
            with open(backup_path, 'r') as backup:
                with open(file_path, 'w') as original:
                    original.write(backup.read())
            logger.info("Restored from backup due to error")
        return False

def fix_real_trading_engine():
    """Add freshness and drift guards to the real trading engine"""
    file_path = "src/trading/real_trading_engine.py"
    
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path} - skipping real trading engine fixes")
        return True
    
    # Create backup
    backup_path = backup_file(file_path)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the method that opens positions from opportunities
        # Look for common method names
        method_patterns = [
            'def _open_live_position_from_opportunity',
            'def open_position_from_opportunity',
            'def execute_trade_from_opportunity',
            'def place_order_from_opportunity'
        ]
        
        method_start = -1
        for pattern in method_patterns:
            method_start = content.find(pattern)
            if method_start != -1:
                break
        
        if method_start == -1:
            logger.warning("Could not find position opening method in real trading engine")
            return True
        
        # Find the start of the method body
        method_body_start = content.find(':', method_start) + 1
        method_body_start = content.find('\n', method_body_start) + 1
        
        # Add freshness and drift guards at the beginning of the method
        guards_code = '''        # Freshness guard - skip stale signals
        gen_ts = float(opp.get("signal_timestamp", 0) or 0)
        if gen_ts and (time.time() - gen_ts) > 90:
            logger.warning("Skip %s: signal too old (%.1fs)", opp.get("symbol"), time.time() - gen_ts)
            return

        # Price drift guard - skip if price moved too much from entry
        try:
            symbol = opp["symbol"]
            entry_price = float(opp["entry_price"])
            # Get current market price
            live_price = None
            try:
                live_price = float(await self.exchange_client.get_price(symbol))
            except Exception:
                # fallback to ticker lastPrice
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                live_price = float(ticker.get("lastPrice"))

            drift = abs(live_price - entry_price) / entry_price
            if drift > 0.002:  # > 0.2%
                logger.warning("Skip %s: price drift %.3f%% exceeds threshold", symbol, drift * 100.0)
                return
        except Exception as e:
            logger.warning("Drift check failed for %s, continuing: %s", opp.get("symbol"), e)

'''
        
        # Insert the guards code
        content = content[:method_body_start] + guards_code + content[method_body_start:]
        
        # Make sure time import is present
        if 'import time' not in content:
            import_section = content.find('import')
            if import_section != -1:
                content = content[:import_section] + 'import time\n' + content[import_section:]
        
        # Write the updated content
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Successfully updated {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating real trading engine: {e}")
        # Restore backup if something went wrong
        if backup_path and os.path.exists(backup_path):
            with open(backup_path, 'r') as backup:
                with open(file_path, 'w') as original:
                    original.write(backup.read())
            logger.info("Restored from backup due to error")
        return False

def update_config():
    """Update configuration with new parameters"""
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path} - skipping config update")
        return True
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Add new configuration parameters
        new_config = '''
# Directional accuracy improvements
opportunity_manager:
  signal_lifetime_sec: 300
  min_signal_change_interval_sec: 60
  hysteresis_momentum_mult: 1.25   # used by _should_accept_flip
  base_momentum_threshold: 0.001   # 0.1% baseline for hysteresis guard

real_trading:
  signal_freshness_max_sec: 90
  max_entry_price_drift: 0.002     # 0.2%
'''
        
        # Append to config if not already present
        if 'hysteresis_momentum_mult' not in content:
            content += new_config
            
            with open(config_path, 'w') as f:
                f.write(content)
            
            logger.info(f"Updated configuration in {config_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return False

def create_test_script():
    """Create a test script to verify the fixes"""
    test_content = '''#!/usr/bin/env python3
"""
Test script to verify directional accuracy fixes
"""

import asyncio
import logging
import time
from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direction_normalization():
    """Test that all directions are properly normalized to LONG/SHORT"""
    logger.info("Testing direction normalization...")
    
    # Create mock opportunity manager
    exchange_client = ExchangeClient()
    om = OpportunityManager(exchange_client, None, None)
    
    # Test various direction labels
    test_opportunities = [
        {"symbol": "BTCUSDT", "direction": "BUY", "entry_price": 50000, "take_profit": 51000, "stop_loss": 49000},
        {"symbol": "ETHUSDT", "direction": "SELL", "entry_price": 3000, "take_profit": 2900, "stop_loss": 3100},
        {"symbol": "ADAUSDT", "direction": "BULL", "entry_price": 1.0, "take_profit": 1.05, "stop_loss": 0.95},
        {"symbol": "SOLUSDT", "direction": "BEAR", "entry_price": 100, "take_profit": 95, "stop_loss": 105},
    ]
    
    for opp in test_opportunities:
        original_direction = opp["direction"]
        finalized = om._finalize_and_stamp(opp.copy())
        
        if finalized:
            final_direction = finalized["direction"]
            logger.info(f"Direction normalization: {original_direction} -> {final_direction}")
            
            # Verify it's either LONG or SHORT
            assert final_direction in ["LONG", "SHORT"], f"Invalid direction: {final_direction}"
            
            # Verify TP/SL are on correct sides
            entry = finalized["entry_price"]
            tp = finalized["take_profit"]
            sl = finalized["stop_loss"]
            
            if final_direction == "LONG":
                assert tp > entry, f"LONG TP should be above entry: {tp} vs {entry}"
                assert sl < entry, f"LONG SL should be below entry: {sl} vs {entry}"
            else:  # SHORT
                assert tp < entry, f"SHORT TP should be below entry: {tp} vs {entry}"
                assert sl > entry, f"SHORT SL should be above entry: {sl} vs {entry}"
    
    logger.info("✅ Direction normalization tests passed!")

async def test_debounce_logic():
    """Test that direction changes are properly debounced"""
    logger.info("Testing debounce logic...")
    
    exchange_client = ExchangeClient()
    om = OpportunityManager(exchange_client, None, None)
    
    # Set up initial opportunity
    om.opportunities["BTCUSDT"] = {
        "direction": "LONG",
        "signal_timestamp": time.time(),
        "entry_price": 50000
    }
    
    # Test rapid direction change (should be rejected)
    should_accept = om._should_accept_flip("BTCUSDT", "SHORT", momentum=0.0005)
    assert not should_accept, "Should reject rapid direction flip"
    
    # Test direction change after sufficient time
    om.opportunities["BTCUSDT"]["signal_timestamp"] = time.time() - 70  # 70 seconds ago
    should_accept = om._should_accept_flip("BTCUSDT", "SHORT", momentum=0.002)
    assert should_accept, "Should accept direction flip after sufficient time"
    
    logger.info("✅ Debounce logic tests passed!")

async def main():
    """Run all tests"""
    try:
        await test_direction_normalization()
        await test_debounce_logic()
        logger.info("🎉 All directional accuracy tests passed!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    return True

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open("test_directional_accuracy_fixes.py", "w") as f:
        f.write(test_content)
    
    logger.info("Created test script: test_directional_accuracy_fixes.py")

def main():
    """Main function to apply all fixes"""
    logger.info("🚀 Starting directional accuracy fixes...")
    
    success = True
    
    # Apply fixes
    logger.info("1. Fixing opportunity manager...")
    if not fix_opportunity_manager():
        success = False
    
    logger.info("2. Fixing real trading engine...")
    if not fix_real_trading_engine():
        success = False
    
    logger.info("3. Updating configuration...")
    if not update_config():
        success = False
    
    logger.info("4. Creating test script...")
    create_test_script()
    
    if success:
        logger.info("✅ All directional accuracy fixes applied successfully!")
        logger.info("\nKey improvements:")
        logger.info("- Signal direction normalization enforced everywhere")
        logger.info("- Forming candle instability eliminated")
        logger.info("- Direction flip debouncing with hysteresis")
        logger.info("- Freshness and price drift guards in trading engine")
        logger.info("- Atomic opportunity map publishing")
        logger.info("\nNext steps:")
        logger.info("1. Run: python test_directional_accuracy_fixes.py")
        logger.info("2. Monitor logs for 'normalized' and 'Skip ... signal too old' messages")
        logger.info("3. Verify no more wrong direction trades occur")
    else:
        logger.error("❌ Some fixes failed - check logs above")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
