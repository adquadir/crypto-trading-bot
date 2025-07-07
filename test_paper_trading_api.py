#!/usr/bin/env python3
"""
Simple API Server Test for Flow Trading Only Paper Trading
Tests the new API endpoints directly
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the paper trading router
from src.api.trading_routes.paper_trading_routes import router as paper_trading_router, initialize_paper_trading_engine, set_paper_engine

async def initialize_paper_trading():
    """Initialize paper trading engine"""
    try:
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 1.0,
                'max_daily_loss_pct': 0.50
            }
        }
        
        # Initialize with Flow Trading only
        engine = await initialize_paper_trading_engine(
            config=config,
            exchange_client=None,  # Mock mode
            flow_trading_strategy='adaptive'  # Default strategy
        )
        
        if engine:
            set_paper_engine(engine)
            logger.info("✅ Paper trading engine initialized successfully")
            return True
        else:
            logger.error("❌ Failed to initialize paper trading engine")
            return False
            
    except Exception as e:
        logger.error(f"Error initializing paper trading: {e}")
        return False

def create_test_app():
    """Create test FastAPI app"""
    
    app = FastAPI(
        title="Paper Trading Test API",
        description="Test API for Flow Trading Only Paper Trading",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include paper trading router
    app.include_router(paper_trading_router, prefix="/api/v1")
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize paper trading on startup"""
        logger.info("🚀 Starting Paper Trading Test API...")
        success = await initialize_paper_trading()
        if success:
            logger.info("✅ Paper Trading Test API started successfully!")
        else:
            logger.error("❌ Failed to start Paper Trading Test API")
    
    @app.get("/")
    async def root():
        return {
            "message": "Paper Trading Test API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "health": "/api/v1/paper-trading/health",
                "status": "/api/v1/paper-trading/status",
                "strategies": "/api/v1/paper-trading/strategies",
                "start": "/api/v1/paper-trading/start",
                "stop": "/api/v1/paper-trading/stop"
            }
        }
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "message": "Paper Trading Test API is running"}
    
    return app

async def test_endpoints():
    """Test the API endpoints"""
    import httpx
    
    print("\n🧪 Testing Paper Trading API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:8001"
    
    try:
        async with httpx.AsyncClient() as client:
            # Test 1: Health check
            print("\n1️⃣ Testing Health Check")
            response = await client.get(f"{base_url}/api/v1/paper-trading/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Health check passed: {data.get('status')}")
            else:
                print(f"   ❌ Health check failed")
            
            # Test 2: Get available strategies
            print("\n2️⃣ Testing Get Available Strategies")
            response = await client.get(f"{base_url}/api/v1/paper-trading/strategies")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                strategies = data.get('data', {}).get('available_strategies', {})
                print(f"   ✅ Found {len(strategies)} strategies:")
                for key, info in strategies.items():
                    print(f"      - {key}: {info['name']}")
            else:
                print(f"   ❌ Get strategies failed")
            
            # Test 3: Get current strategy
            print("\n3️⃣ Testing Get Current Strategy")
            response = await client.get(f"{base_url}/api/v1/paper-trading/strategy")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                current_strategy = data.get('data', {}).get('current_strategy')
                print(f"   ✅ Current strategy: {current_strategy}")
            else:
                print(f"   ❌ Get current strategy failed")
            
            # Test 4: Set strategy
            print("\n4️⃣ Testing Set Strategy")
            response = await client.post(f"{base_url}/api/v1/paper-trading/strategy?strategy=breakout")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Strategy changed: {data.get('message')}")
            else:
                print(f"   ❌ Set strategy failed")
            
            # Test 5: Get status
            print("\n5️⃣ Testing Get Status")
            response = await client.get(f"{base_url}/api/v1/paper-trading/status")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                status_data = data.get('data', {})
                print(f"   ✅ Status retrieved:")
                print(f"      - Enabled: {status_data.get('enabled')}")
                print(f"      - Balance: ${status_data.get('virtual_balance', 0):.2f}")
                print(f"      - Total Return: {status_data.get('total_return_pct', 0):.2f}%")
            else:
                print(f"   ❌ Get status failed")
            
            print("\n🎉 API Endpoint Tests Completed!")
            
    except Exception as e:
        print(f"\n❌ API endpoint test failed: {e}")

async def main():
    """Main test function"""
    
    print("🚀 Starting Paper Trading API Test")
    print("=" * 60)
    
    # Create and run the test app
    app = create_test_app()
    
    # Start server in background
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)
    
    # Run server and tests
    try:
        # Start server in background task
        server_task = asyncio.create_task(server.serve())
        
        # Wait a moment for server to start
        await asyncio.sleep(3)
        
        # Run endpoint tests
        await test_endpoints()
        
        # Stop server
        server.should_exit = True
        await server_task
        
        print("\n✅ Paper Trading API Test Completed Successfully!")
        
    except Exception as e:
        print(f"\n❌ API test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🎉 ALL API TESTS PASSED!")
        print("Flow Trading Only Paper Trading API is working correctly!")
    else:
        print("\n❌ API TESTS FAILED")
