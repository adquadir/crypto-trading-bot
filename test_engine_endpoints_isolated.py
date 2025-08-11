#!/usr/bin/env python3
"""
Isolated test to verify engine toggle endpoints work independently
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.testclient import TestClient

def test_endpoints_isolated():
    """Test the endpoints in complete isolation"""
    print("🧪 Testing engine toggle endpoints in isolation...")
    
    try:
        # Import the router directly
        from src.api.trading_routes.paper_trading_routes import router as paper_trading_router
        print("✅ Successfully imported paper_trading_router")
        
        # Create minimal FastAPI app
        app = FastAPI(title="Engine Toggle Test")
        app.include_router(paper_trading_router, prefix="/api/v1")
        
        # Create test client
        client = TestClient(app)
        print("✅ Created test client")
        
        # Test GET engines endpoint
        print("\n🔍 Testing GET /api/v1/paper-trading/engines...")
        response = client.get("/api/v1/paper-trading/engines")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ GET engines endpoint works!")
            data = response.json()
            print(f"Data: {data}")
        else:
            print(f"❌ GET engines endpoint failed: {response.status_code}")
            return False
        
        # Test POST engine-toggle endpoint
        print("\n🔍 Testing POST /api/v1/paper-trading/engine-toggle...")
        response = client.post("/api/v1/paper-trading/engine-toggle", json={
            "engine": "opportunity_manager",
            "enabled": False
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ POST engine-toggle endpoint works!")
            data = response.json()
            print(f"Data: {data}")
        else:
            print(f"❌ POST engine-toggle endpoint failed: {response.status_code}")
            return False
        
        print("\n🎉 ALL ENDPOINTS WORK IN ISOLATION!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎯 Engine Toggle Endpoints - Isolated Testing")
    print("=" * 50)
    
    # Test with TestClient
    test_endpoints_isolated()
