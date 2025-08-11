#!/usr/bin/env python3
"""
Test the new engine toggle endpoints directly by importing the routes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all imports work"""
    print("🧪 Testing imports...")
    
    try:
        from src.trading.signal_config import get_signal_config, set_signal_config
        print("✅ signal_config imports work")
        
        config = get_signal_config()
        print(f"✅ Current config: {config}")
        
    except Exception as e:
        print(f"❌ signal_config import failed: {e}")
        return False
    
    try:
        from src.api.trading_routes.paper_trading_routes import router
        print("✅ paper_trading_routes imports work")
        
        # List all routes
        routes = [route.path for route in router.routes if hasattr(route, 'path')]
        print(f"✅ Router has {len(routes)} routes:")
        for route in routes:
            print(f"  - {route}")
            
        # Check if our new endpoints are there
        if '/engines' in routes:
            print("✅ /engines endpoint found!")
        else:
            print("❌ /engines endpoint NOT found!")
            
        if '/engine-toggle' in routes:
            print("✅ /engine-toggle endpoint found!")
        else:
            print("❌ /engine-toggle endpoint NOT found!")
            
    except Exception as e:
        print(f"❌ paper_trading_routes import failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Testing Engine Toggle Endpoints Implementation")
    print("=" * 60)
    
    imports_ok = test_imports()
    
    if imports_ok:
        print("\n🎉 IMPORTS PASSED!")
        print("✅ The endpoints should be available")
    else:
        print("\n❌ IMPORT TESTS FAILED!")
