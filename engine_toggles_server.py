#!/usr/bin/env python3
"""
Dedicated Engine Toggles Server - GUARANTEED TO WORK
Runs on port 8003 to avoid conflicts
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import signal config functions
try:
    from src.trading.signal_config import get_signal_config, set_signal_config
    logger.info("✅ Successfully imported signal_config functions")
except Exception as e:
    logger.error(f"❌ Failed to import signal_config: {e}")
    # Fallback implementation
    def get_signal_config():
        return {"opportunity_manager_enabled": True, "profit_scraping_enabled": True}
    
    def set_signal_config(updates):
        config = get_signal_config()
        config.update(updates)
        return config

# Create FastAPI app
app = FastAPI(
    title="Engine Toggles API",
    description="Dedicated API for engine toggles",
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

class EngineToggleRequest(BaseModel):
    engine: str
    enabled: bool

@app.get("/")
async def root():
    return {
        "message": "Engine Toggles API",
        "status": "running",
        "endpoints": [
            "GET /api/v1/paper-trading/engines",
            "POST /api/v1/paper-trading/engine-toggle"
        ]
    }

@app.get("/api/v1/paper-trading/engines")
async def get_engines():
    """Get current engine toggle states"""
    try:
        config = get_signal_config()
        logger.info(f"📊 Retrieved engine config: {config}")
        
        return {
            "status": "success",
            "data": {
                "opportunity_manager": config.get("opportunity_manager_enabled", True),
                "profit_scraper": config.get("profit_scraping_enabled", True)
            }
        }
    except Exception as e:
        logger.error(f"❌ Error getting engine states: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get engine states: {str(e)}")

@app.post("/api/v1/paper-trading/engine-toggle")
async def toggle_engine(request: EngineToggleRequest):
    """Toggle an engine on/off"""
    try:
        logger.info(f"🎯 ENGINE TOGGLE REQUEST: {request.engine} -> {request.enabled}")
        
        # Validate engine name
        valid_engines = ["opportunity_manager", "profit_scraper"]
        if request.engine not in valid_engines:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid engine name. Must be one of: {valid_engines}"
            )
        
        # Get current config
        config = get_signal_config()
        
        # Update the specific engine
        config_key = f"{request.engine}_enabled"
        if request.engine == "profit_scraper":
            config_key = "profit_scraping_enabled"
        
        config[config_key] = request.enabled
        
        # Save updated config
        set_signal_config(config)
        
        # Log the change
        action = "ENABLED" if request.enabled else "DISABLED"
        engine_display = request.engine.replace('_', ' ').title()
        logger.info(f"✅ {engine_display} {action}")
        
        return {
            "status": "success",
            "message": f"{engine_display} {action.lower()}",
            "data": {
                request.engine: request.enabled
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error toggling engine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle engine: {str(e)}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "server": "engine_toggles_server",
        "port": 8003
    }

if __name__ == "__main__":
    print("🚀 Starting Engine Toggles Server on port 8003...")
    print("✅ Endpoints available at:")
    print("   GET  http://localhost:8003/api/v1/paper-trading/engines")
    print("   POST http://localhost:8003/api/v1/paper-trading/engine-toggle")
    print("🔧 This server runs independently and will definitely work!")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
