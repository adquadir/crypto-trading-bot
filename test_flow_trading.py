#!/usr/bin/env python3
"""
Flow Trading Implementation Test Script
Tests all components of the flow trading system
"""

import asyncio
import logging
import requests
import json
from datetime import datetime
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"

class FlowTradingTester:
    """Test suite for flow trading implementation"""
    
    def __init__(self):
        self.test_results = []
        
    def log_test_result(self, test_name: str, success: bool, message: str = ""):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status}: {test_name} - {message}")
        
    def test_api_endpoint(self, endpoint: str, expected_status: int = 200) -> bool:
        """Test API endpoint accessibility"""
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            success = response.status_code == expected_status
            
            if success:
                self.log_test_result(f"API {endpoint}", True, f"Status: {response.status_code}")
                return True
            else:
                self.log_test_result(f"API {endpoint}", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result(f"API {endpoint}", False, f"Error: {str(e)}")
            return False
    
    def test_flow_trading_status(self) -> bool:
        """Test flow trading status endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/flow-trading/status", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['enabled', 'active_strategies', 'active_grids', 'active_scalping']
                
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_test_result("Flow Trading Status", True, f"All fields present: {list(data.keys())}")
                    return True
                else:
                    self.log_test_result("Flow Trading Status", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_test_result("Flow Trading Status", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Flow Trading Status", False, f"Error: {str(e)}")
            return False
    
    def test_strategy_management(self) -> bool:
        """Test strategy management endpoints"""
        try:
            # Test getting strategies
            response = requests.get(f"{BASE_URL}/flow-trading/strategies", timeout=5)
            
            if response.status_code == 200:
                strategies = response.json()
                self.log_test_result("Get Strategies", True, f"Retrieved {len(strategies)} strategies")
                
                # Test adding a strategy
                test_symbol = "BTCUSDT"
                add_response = requests.post(f"{BASE_URL}/flow-trading/strategies/{test_symbol}/start", timeout=5)
                
                if add_response.status_code == 200:
                    self.log_test_result("Add Strategy", True, f"Added strategy for {test_symbol}")
                    
                    # Test stopping the strategy
                    stop_response = requests.post(f"{BASE_URL}/flow-trading/strategies/{test_symbol}/stop", timeout=5)
                    
                    if stop_response.status_code == 200:
                        self.log_test_result("Stop Strategy", True, f"Stopped strategy for {test_symbol}")
                        return True
                    else:
                        self.log_test_result("Stop Strategy", False, f"HTTP {stop_response.status_code}")
                        return False
                else:
                    self.log_test_result("Add Strategy", False, f"HTTP {add_response.status_code}")
                    return False
            else:
                self.log_test_result("Get Strategies", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Strategy Management", False, f"Error: {str(e)}")
            return False
    
    def test_grid_trading(self) -> bool:
        """Test grid trading endpoints"""
        try:
            # Test getting grids
            response = requests.get(f"{BASE_URL}/flow-trading/grids", timeout=5)
            
            if response.status_code == 200:
                grids = response.json()
                self.log_test_result("Get Grids", True, f"Retrieved {len(grids)} grids")
                
                # Test starting a grid
                test_symbol = "ETHUSDT"
                grid_config = {
                    "symbol": test_symbol,
                    "levels": 5,
                    "spacing_multiplier": 1.0,
                    "position_size_usd": 50.0
                }
                
                start_response = requests.post(
                    f"{BASE_URL}/flow-trading/grids/{test_symbol}/start",
                    json=grid_config,
                    timeout=5
                )
                
                if start_response.status_code == 200:
                    self.log_test_result("Start Grid", True, f"Started grid for {test_symbol}")
                    
                    # Test stopping the grid
                    stop_response = requests.post(f"{BASE_URL}/flow-trading/grids/{test_symbol}/stop", timeout=5)
                    
                    if stop_response.status_code == 200:
                        self.log_test_result("Stop Grid", True, f"Stopped grid for {test_symbol}")
                        return True
                    else:
                        self.log_test_result("Stop Grid", False, f"HTTP {stop_response.status_code}")
                        return False
                else:
                    self.log_test_result("Start Grid", False, f"HTTP {start_response.status_code}")
                    return False
            else:
                self.log_test_result("Get Grids", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Grid Trading", False, f"Error: {str(e)}")
            return False
    
    def test_risk_metrics(self) -> bool:
        """Test risk metrics endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/flow-trading/risk", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test_result("Risk Metrics", True, f"Retrieved risk data: {list(data.keys())}")
                return True
            else:
                self.log_test_result("Risk Metrics", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Risk Metrics", False, f"Error: {str(e)}")
            return False
    
    def test_performance_metrics(self) -> bool:
        """Test performance metrics endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/flow-trading/performance", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test_result("Performance Metrics", True, f"Retrieved performance data")
                return True
            else:
                self.log_test_result("Performance Metrics", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Performance Metrics", False, f"Error: {str(e)}")
            return False
    
    def test_emergency_stop(self) -> bool:
        """Test emergency stop functionality"""
        try:
            response = requests.post(f"{BASE_URL}/flow-trading/emergency-stop", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test_result("Emergency Stop", True, f"Emergency stop executed")
                return True
            else:
                self.log_test_result("Emergency Stop", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("Emergency Stop", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all flow trading tests"""
        logger.info("🚀 Starting Flow Trading Implementation Tests")
        logger.info("=" * 60)
        
        # Test basic connectivity - expect 200 for health endpoint
        self.test_api_endpoint("/health", 200)
        
        # Test flow trading endpoints
        self.test_flow_trading_status()
        self.test_strategy_management()
        self.test_grid_trading()
        self.test_risk_metrics()
        self.test_performance_metrics()
        self.test_emergency_stop()
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 60)
        logger.info("📊 FLOW TRADING IMPLEMENTATION TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests} ✅")
        logger.info(f"Failed: {failed_tests} ❌")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    logger.info(f"  - {result['test']}: {result['message']}")
        
        logger.info("\n🎯 FLOW TRADING IMPLEMENTATION STATUS:")
        if passed_tests >= total_tests * 0.8:  # 80% pass rate
            logger.info("✅ IMPLEMENTATION SUCCESSFUL - Flow trading is working!")
        else:
            logger.info("❌ IMPLEMENTATION NEEDS ATTENTION - Some components failed")
        
        # Save detailed results
        with open('flow_trading_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"\n📝 Detailed results saved to: flow_trading_test_results.json")

def main():
    """Main test runner"""
    tester = FlowTradingTester()
    
    # Wait a moment for server to be ready
    logger.info("⏳ Waiting for server to be ready...")
    time.sleep(3)
    
    tester.run_all_tests()

if __name__ == "__main__":
    main() 