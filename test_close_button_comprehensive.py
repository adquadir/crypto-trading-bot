#!/usr/bin/env python3
"""
Comprehensive Close Button Test
Tests the complete close button functionality from frontend to backend
"""

import asyncio
import requests
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = "http://localhost:8000"

class CloseButtonTester:
    def __init__(self):
        self.api_base = API_BASE_URL
        self.session = requests.Session()
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_api_connection(self):
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{self.api_base}/api/v1/paper-trading/health")
            if response.status_code == 200:
                self.log_test("API Connection", True, f"Status: {response.status_code}")
                return True
            else:
                self.log_test("API Connection", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("API Connection", False, f"Error: {e}")
            return False
    
    def start_paper_trading(self):
        """Start paper trading engine"""
        try:
            response = self.session.post(f"{self.api_base}/api/v1/paper-trading/start")
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == 'success':
                self.log_test("Start Paper Trading", True, "Engine started successfully")
                return True
            else:
                self.log_test("Start Paper Trading", False, f"Response: {data}")
                return False
        except Exception as e:
            self.log_test("Start Paper Trading", False, f"Error: {e}")
            return False
    
    def create_test_position(self):
        """Create a test position for closing"""
        try:
            # Create a manual trade
            trade_data = {
                "symbol": "BTCUSDT",
                "strategy_type": "test",
                "side": "LONG",
                "confidence": 0.8,
                "reason": "close_button_test",
                "market_regime": "test",
                "volatility_regime": "medium"
            }
            
            response = self.session.post(
                f"{self.api_base}/api/v1/paper-trading/trade",
                json=trade_data
            )
            data = response.json()
            
            if response.status_code == 200 and data.get('position_id'):
                position_id = data['position_id']
                self.log_test("Create Test Position", True, f"Position ID: {position_id}")
                return position_id
            else:
                self.log_test("Create Test Position", False, f"Response: {data}")
                return None
        except Exception as e:
            self.log_test("Create Test Position", False, f"Error: {e}")
            return None
    
    def get_active_positions(self):
        """Get list of active positions"""
        try:
            response = self.session.get(f"{self.api_base}/api/v1/paper-trading/positions")
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == 'success':
                positions = data.get('data', [])
                self.log_test("Get Active Positions", True, f"Found {len(positions)} positions")
                return positions
            else:
                self.log_test("Get Active Positions", False, f"Response: {data}")
                return []
        except Exception as e:
            self.log_test("Get Active Positions", False, f"Error: {e}")
            return []
    
    def test_close_position(self, position_id: str):
        """Test closing a specific position"""
        try:
            logger.info(f"🔄 Testing close for position: {position_id}")
            
            # Test the close endpoint
            close_data = {"exit_reason": "test_close"}
            response = self.session.post(
                f"{self.api_base}/api/v1/paper-trading/positions/{position_id}/close",
                json=close_data
            )
            
            logger.info(f"📥 Close response status: {response.status_code}")
            
            try:
                data = response.json()
                logger.info(f"📋 Close response data: {json.dumps(data, indent=2)}")
            except:
                logger.error(f"❌ Failed to parse response as JSON: {response.text}")
                self.log_test("Close Position", False, "Invalid JSON response")
                return False
            
            if response.status_code == 200 and data.get('status') == 'success':
                trade_info = data.get('trade', {})
                pnl = trade_info.get('pnl', 0)
                self.log_test("Close Position", True, f"P&L: ${pnl:.2f}")
                return True
            elif response.status_code == 404:
                self.log_test("Close Position", False, "Position not found (404)")
                return False
            elif response.status_code == 409:
                self.log_test("Close Position", False, "Position already closed (409)")
                return False
            else:
                error_detail = data.get('detail', 'Unknown error')
                self.log_test("Close Position", False, f"Status {response.status_code}: {error_detail}")
                return False
                
        except Exception as e:
            self.log_test("Close Position", False, f"Exception: {e}")
            return False
    
    def test_close_nonexistent_position(self):
        """Test closing a position that doesn't exist"""
        try:
            fake_position_id = "fake-position-12345"
            close_data = {"exit_reason": "test_nonexistent"}
            
            response = self.session.post(
                f"{self.api_base}/api/v1/paper-trading/positions/{fake_position_id}/close",
                json=close_data
            )
            
            if response.status_code == 404:
                self.log_test("Close Nonexistent Position", True, "Correctly returned 404")
                return True
            else:
                data = response.json()
                self.log_test("Close Nonexistent Position", False, f"Expected 404, got {response.status_code}: {data}")
                return False
                
        except Exception as e:
            self.log_test("Close Nonexistent Position", False, f"Exception: {e}")
            return False
    
    def test_close_invalid_position_id(self):
        """Test closing with invalid position ID formats"""
        invalid_ids = ["", " ", "null", "undefined", None]
        
        for invalid_id in invalid_ids:
            try:
                if invalid_id is None:
                    url = f"{self.api_base}/api/v1/paper-trading/positions/None/close"
                else:
                    url = f"{self.api_base}/api/v1/paper-trading/positions/{invalid_id}/close"
                
                close_data = {"exit_reason": "test_invalid"}
                response = self.session.post(url, json=close_data)
                
                if response.status_code in [400, 404]:
                    self.log_test(f"Close Invalid ID '{invalid_id}'", True, f"Correctly rejected with {response.status_code}")
                else:
                    data = response.json()
                    self.log_test(f"Close Invalid ID '{invalid_id}'", False, f"Expected 400/404, got {response.status_code}: {data}")
                    
            except Exception as e:
                self.log_test(f"Close Invalid ID '{invalid_id}'", False, f"Exception: {e}")
    
    def test_double_close(self, position_id: str):
        """Test closing the same position twice"""
        try:
            # First close
            close_data = {"exit_reason": "first_close"}
            response1 = self.session.post(
                f"{self.api_base}/api/v1/paper-trading/positions/{position_id}/close",
                json=close_data
            )
            
            # Second close (should fail)
            close_data = {"exit_reason": "second_close"}
            response2 = self.session.post(
                f"{self.api_base}/api/v1/paper-trading/positions/{position_id}/close",
                json=close_data
            )
            
            if response1.status_code == 200 and response2.status_code in [404, 409]:
                self.log_test("Double Close Protection", True, f"First: {response1.status_code}, Second: {response2.status_code}")
                return True
            else:
                self.log_test("Double Close Protection", False, f"First: {response1.status_code}, Second: {response2.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Double Close Protection", False, f"Exception: {e}")
            return False
    
    def verify_position_removed(self, position_id: str):
        """Verify that a closed position is removed from active positions"""
        try:
            positions = self.get_active_positions()
            position_ids = [pos.get('id') for pos in positions]
            
            if position_id not in position_ids:
                self.log_test("Position Removal Verification", True, "Position correctly removed from active list")
                return True
            else:
                self.log_test("Position Removal Verification", False, "Position still in active list")
                return False
                
        except Exception as e:
            self.log_test("Position Removal Verification", False, f"Exception: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run all close button tests"""
        logger.info("🚀 Starting Comprehensive Close Button Test")
        logger.info("=" * 60)
        
        # Test 1: API Connection
        if not self.test_api_connection():
            logger.error("❌ API connection failed - aborting tests")
            return False
        
        # Test 2: Start Paper Trading
        if not self.start_paper_trading():
            logger.error("❌ Failed to start paper trading - aborting tests")
            return False
        
        # Wait for engine to fully start
        time.sleep(2)
        
        # Test 3: Invalid Position ID Tests
        logger.info("\n🔍 Testing Invalid Position IDs...")
        self.test_close_invalid_position_id()
        
        # Test 4: Nonexistent Position Test
        logger.info("\n🔍 Testing Nonexistent Position...")
        self.test_close_nonexistent_position()
        
        # Test 5: Create Test Position
        logger.info("\n🔍 Creating Test Position...")
        position_id = self.create_test_position()
        if not position_id:
            logger.error("❌ Failed to create test position - skipping position-specific tests")
        else:
            # Test 6: Get Active Positions
            logger.info("\n🔍 Getting Active Positions...")
            positions = self.get_active_positions()
            
            # Test 7: Close Valid Position
            logger.info(f"\n🔍 Testing Close Valid Position ({position_id})...")
            close_success = self.test_close_position(position_id)
            
            if close_success:
                # Test 8: Verify Position Removal
                logger.info("\n🔍 Verifying Position Removal...")
                self.verify_position_removed(position_id)
                
                # Test 9: Double Close Protection
                logger.info("\n🔍 Testing Double Close Protection...")
                self.test_double_close(position_id)
        
        # Create another position for double close test
        logger.info("\n🔍 Creating Second Test Position for Double Close Test...")
        position_id2 = self.create_test_position()
        if position_id2:
            time.sleep(1)  # Brief delay
            self.test_double_close(position_id2)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests} ✅")
        logger.info(f"Failed: {failed_tests} ❌")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    logger.info(f"  - {result['test']}: {result['details']}")
        
        return failed_tests == 0

def main():
    """Main test function"""
    tester = CloseButtonTester()
    success = tester.run_comprehensive_test()
    
    if success:
        logger.info("\n🎉 ALL TESTS PASSED! Close button functionality is working correctly.")
        exit(0)
    else:
        logger.error("\n💥 SOME TESTS FAILED! Close button needs attention.")
        exit(1)

if __name__ == "__main__":
    main()
