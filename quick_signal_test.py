#!/usr/bin/env python3
"""
Quick test to verify balanced signal generation
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from src.strategies.profit_scraping.price_level_analyzer import PriceLevelAnalyzer

async def main():
    print("🧪 Testing balanced signal generation...")
    
    analyzer = PriceLevelAnalyzer(min_touches=2, min_strength=50)
    
    # Test a few symbols
    symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    
    total_support = 0
    total_resistance = 0
    
    for symbol in symbols:
        print(f"\n🔍 Testing {symbol}...")
        
        levels = await analyzer.analyze_symbol(symbol, exchange_client=None)
        
        support_count = sum(1 for level in levels if level.level_type == 'support')
        resistance_count = sum(1 for level in levels if level.level_type == 'resistance')
        
        total_support += support_count
        total_resistance += resistance_count
        
        print(f"  📈 Support levels (LONG): {support_count}")
        print(f"  📉 Resistance levels (SHORT): {resistance_count}")
        
        for level in levels:
            direction = "LONG" if level.level_type == 'support' else "SHORT"
            print(f"    {direction} @ ${level.price:.2f} (strength: {level.strength_score})")
    
    print(f"\n📊 SUMMARY:")
    print(f"  Total LONG signals: {total_support}")
    print(f"  Total SHORT signals: {total_resistance}")
    
    if total_resistance > 0:
        print("✅ SUCCESS: System generates both LONG and SHORT signals!")
    else:
        print("❌ ISSUE: No SHORT signals generated")

if __name__ == "__main__":
    asyncio.run(main())
