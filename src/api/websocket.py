from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import asyncio
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from src.api.connection_manager import ConnectionManager
from urllib.parse import parse_qs

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/web_interface.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize connection manager
manager = ConnectionManager()

# Global components (will be set from main.py)
opportunity_manager = None
exchange_client = None
enhanced_signal_tracker = None

def set_websocket_components(opp_mgr, exch_client, signal_tracker=None):
    """Set the component instances for WebSocket use."""
    global opportunity_manager, exchange_client, enhanced_signal_tracker
    opportunity_manager = opp_mgr
    exchange_client = exch_client
    enhanced_signal_tracker = signal_tracker

async def validate_api_key(api_key: str) -> bool:
    """Validate the provided API key against the environment variable."""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        logger.warning("API_KEY environment variable not set")
        return False
    return api_key == expected_key

async def get_live_tracking_data():
    """Get live tracking data for WebSocket streaming"""
    try:
        if not enhanced_signal_tracker:
            return {
                "active_signals_count": 0,
                "price_cache_symbols": 0,
                "active_signals": []
            }
        
        active_count = len(enhanced_signal_tracker.active_signals)
        
        # Get summary of active signals
        active_summary = []
        for signal_id, signal_data in enhanced_signal_tracker.active_signals.items():
            current_price = enhanced_signal_tracker.price_cache.get(signal_data['symbol'], 0)
            
            # Calculate current PnL
            if current_price > 0:
                entry_price = signal_data['entry_price']
                direction = signal_data['direction']
                
                if direction == 'LONG':
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
            else:
                pnl_pct = 0
            
            active_summary.append({
                'signal_id': signal_id[:8] + '...',
                'symbol': signal_data['symbol'],
                'strategy': signal_data['strategy'],
                'direction': signal_data['direction'],
                'age_minutes': int((datetime.now() - signal_data['entry_time']).total_seconds() / 60),
                'current_pnl_pct': round(pnl_pct * 100, 2),
                'targets_hit': signal_data['targets_hit'],
                'max_profit_pct': round(signal_data['max_profit'] * 100, 2)
            })
        
        return {
            "active_signals_count": active_count,
            "price_cache_symbols": len(enhanced_signal_tracker.price_cache),
            "active_signals": active_summary
        }
        
    except Exception as e:
        logger.error(f"Error getting live tracking data: {e}")
        return {
            "active_signals_count": 0,
            "price_cache_symbols": 0,
            "active_signals": []
        }

@router.websocket("/ws")
@router.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time trading signals and live tracking data."""
    try:
        # Get query parameters from the URL before accepting
        query_string = websocket.url.query
        query_params = parse_qs(query_string)
        
        # Extract and validate API key
        api_key = query_params.get('api_key', [None])[0]
        if not api_key:
            logger.warning(f"Missing API key from {websocket.client.host}")
            await websocket.close(code=1008, reason="Missing API key")
            return
            
        if not await validate_api_key(api_key):
            logger.warning(f"Invalid API key attempt from {websocket.client.host}")
            await websocket.close(code=1008, reason="Invalid API key")
            return

        # Accept the connection after validation
        await websocket.accept()
        logger.info(f"Client connected with valid API key from {websocket.client.host}")
        
        # Add to connection manager
        await manager.connect(websocket)
        logger.info("WebSocket connection established")
        
        try:
            while True:
                # Prepare the data payload
                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "opportunities": [],
                    "live_tracking": {}
                }
                
                # Check if components are ready
                if not opportunity_manager:
                    await websocket.send_json({
                        "status": "initializing",
                        "message": "Components still initializing...",
                        "data": payload
                    })
                    await asyncio.sleep(5)
                    continue
                
                # Get opportunities from the initialized manager
                try:
                    opportunities = opportunity_manager.get_opportunities()
                    if opportunities:
                        # Handle both dict and list returns
                        if isinstance(opportunities, dict):
                            opportunity_list = list(opportunities.values())
                        else:
                            opportunity_list = opportunities
                            
                        formatted_opportunities = [
                            {
                                'symbol': opp.get('symbol', 'Unknown'),
                                'strategy': opp.get('strategy', 'Unknown'),
                                'timestamp': opp.get('timestamp', ''),
                                'price': opp.get('price', 0),
                                'volume': opp.get('volume', 0),
                                'volatility': opp.get('volatility', 0),
                                'spread': opp.get('spread', 0),
                                'score': opp.get('score', 0)
                            }
                            for opp in opportunity_list
                        ]
                        payload["opportunities"] = formatted_opportunities
                        
                except Exception as e:
                    logger.error(f"Error getting opportunities: {e}")
                    payload["opportunities"] = []
                
                # Get live tracking data
                try:
                    live_tracking_data = await get_live_tracking_data()
                    payload["live_tracking"] = live_tracking_data
                except Exception as e:
                    logger.error(f"Error getting live tracking data: {e}")
                    payload["live_tracking"] = {
                        "active_signals_count": 0,
                        "price_cache_symbols": 0,
                        "active_signals": []
                    }
                
                # Send the complete payload
                await websocket.send_json({
                    "status": "success",
                    "message": f"Live data: {len(payload['opportunities'])} opportunities, {payload['live_tracking']['active_signals_count']} active signals",
                    "data": payload
                })
                
                await asyncio.sleep(2)  # Send updates every 2 seconds
                
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in WebSocket loop: {e}")
            await websocket.send_json({
                "status": "error",
                "message": f"Internal error: {str(e)}",
                "data": {
                    "opportunities": [],
                    "live_tracking": {}
                }
            })
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            if not websocket.client_state.DISCONNECTED:
                await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
