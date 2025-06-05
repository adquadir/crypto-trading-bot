#!/usr/bin/env python3
import argparse
import asyncio
import aiohttp
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('health_check.log')
    ]
)
logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self):
        self.frontend_url = "http://localhost:3000"
        self.api_url = "http://localhost:8000"
        self.ws_url = "ws://localhost:8000/ws"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "frontend": {},
            "api": {},
            "websocket": {},
            "database": {}
        }

    async def check_frontend_pages(self) -> Dict:
        """Check all frontend pages for availability."""
        pages = [
            "/",
            "/opportunities",
            "/signals",
            "/positions",
            "/strategies",
            "/settings",
            "/monitoring",
            "/health"
        ]
        
        results = {}
        async with aiohttp.ClientSession() as session:
            for page in pages:
                try:
                    start_time = datetime.now()
                    async with session.get(f"{self.frontend_url}{page}") as response:
                        load_time = (datetime.now() - start_time).total_seconds()
                        results[page] = {
                            "status": response.status,
                            "load_time": load_time,
                            "error": None if response.status == 200 else f"Status {response.status}"
                        }
                except Exception as e:
                    results[page] = {
                        "status": None,
                        "load_time": None,
                        "error": str(e)
                    }
        return results

    async def check_api_endpoints(self) -> Dict:
        """Check all API endpoints for availability."""
        endpoints = [
            "/api/trading/opportunities",
            "/api/trading/signals",
            "/api/trading/pnl",
            "/api/trading/stats",
            "/api/trading/positions",
            "/api/trading/strategies",
            "/api/trading/settings"
        ]
        
        results = {}
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    start_time = datetime.now()
                    async with session.get(f"{self.api_url}{endpoint}") as response:
                        load_time = (datetime.now() - start_time).total_seconds()
                        results[endpoint] = {
                            "status": response.status,
                            "load_time": load_time,
                            "error": None if response.status == 200 else f"Status {response.status}"
                        }
                except Exception as e:
                    results[endpoint] = {
                        "status": None,
                        "load_time": None,
                        "error": str(e)
                    }
        return results

    async def check_websocket(self) -> Dict:
        """Check WebSocket connections."""
        ws_endpoints = [
            "/ws/signals",
            "/ws/opportunities"
        ]
        
        results = {}
        for endpoint in ws_endpoints:
            try:
                start_time = datetime.now()
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(f"{self.ws_url}{endpoint}") as ws:
                        # Send a ping message
                        await ws.send_json({"type": "ping"})
                        # Wait for pong response
                        response = await ws.receive_json(timeout=5)
                        load_time = (datetime.now() - start_time).total_seconds()
                        results[endpoint] = {
                            "status": "connected",
                            "load_time": load_time,
                            "error": None
                        }
            except Exception as e:
                results[endpoint] = {
                    "status": "disconnected",
                    "load_time": None,
                    "error": str(e)
                }
        return results

    async def check_database(self) -> Dict:
        """Check database connectivity and performance."""
        try:
            from src.database.connection import get_db
            db = get_db()
            
            # Test connection
            start_time = datetime.now()
            await db.execute("SELECT 1")
            load_time = (datetime.now() - start_time).total_seconds()
            
            # Test query performance
            query_start = datetime.now()
            await db.execute("SELECT COUNT(*) FROM opportunities")
            query_time = (datetime.now() - query_start).total_seconds()
            
            return {
                "status": "connected",
                "connection_time": load_time,
                "query_time": query_time,
                "error": None
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "connection_time": None,
                "query_time": None,
                "error": str(e)
            }

    async def run_checks(self, component: Optional[str] = None) -> Dict:
        """Run all health checks or check specific component."""
        if component is None or component == "frontend":
            self.results["frontend"] = await self.check_frontend_pages()
        
        if component is None or component == "api":
            self.results["api"] = await self.check_api_endpoints()
        
        if component is None or component == "websocket":
            self.results["websocket"] = await self.check_websocket()
        
        if component is None or component == "database":
            self.results["database"] = await self.check_database()
        
        return self.results

    def print_results(self):
        """Print health check results in a readable format."""
        print("\n=== Health Check Results ===")
        print(f"Timestamp: {self.results['timestamp']}\n")

        for component, results in self.results.items():
            if component == "timestamp":
                continue
                
            print(f"\n{component.upper()} Health:")
            print("-" * 50)
            
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, dict):
                        print(f"\n{key}:")
                        for k, v in value.items():
                            print(f"  {k}: {v}")
                    else:
                        print(f"{key}: {value}")
            else:
                print(results)
            print()

    def save_results(self):
        """Save health check results to a JSON file."""
        results_dir = Path("health_checks")
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = results_dir / f"health_check_{timestamp}.json"
        
        with open(file_path, "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Health check results saved to {file_path}")

def main():
    parser = argparse.ArgumentParser(description="Verify system health")
    parser.add_argument(
        "--component",
        choices=["frontend", "api", "websocket", "database"],
        help="Check specific component only"
    )
    args = parser.parse_args()

    checker = HealthChecker()
    results = asyncio.run(checker.run_checks(args.component))
    checker.print_results()
    checker.save_results()

if __name__ == "__main__":
    main() 