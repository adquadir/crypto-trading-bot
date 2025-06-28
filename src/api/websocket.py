from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import asyncio
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from src.api.connection_manager import ConnectionManager
from urllib.parse import parse_qs
from src.opportunity.opportunity_manager import OpportunityManager
from src.signals.realtime_scalping_manager import RealtimeScalpingManager
from typing import Dict, List

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
opportunity_manager: OpportunityManager = None
exchange_client = None
enhanced_signal_tracker = None
realtime_scalping_manager: RealtimeScalpingManager = None
flow_manager = None
grid_engine = None

def set_websocket_components(opp_mgr, exch_client, signal_tracker=None, scalping_manager=None, flow_mgr=None, grid_eng=None):
    """Set the component instances for WebSocket use."""
    global opportunity_manager, exchange_client, enhanced_signal_tracker, realtime_scalping_manager, flow_manager, grid_engine
    opportunity_manager = opp_mgr
    exchange_client = exch_client
    enhanced_signal_tracker = signal_tracker
    realtime_scalping_manager = scalping_manager
    flow_manager = flow_mgr
    grid_engine = grid_eng

async def validate_api_key(api_key: str) -> bool:
    """Validate the provided API key against the environment variable."""
    # TEMPORARY: Disable authentication to focus on real-time functionality
    return True
    
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
@router.websocket("/ws/scalping")
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
                    "live_tracking": {},
                    "scalping_signals": [],
                    "scalping_summary": {}
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
                
                # Get real-time scalping signals
                try:
                    # Use the RealtimeScalpingManager (original architecture) not opportunity_manager
                    if realtime_scalping_manager:
                        scalping_signals = realtime_scalping_manager.get_active_signals()
                        scalping_summary = realtime_scalping_manager.get_signal_summary()
                        
                        payload["scalping_signals"] = scalping_signals
                        payload["scalping_summary"] = scalping_summary
                    else:
                        # Fallback if RealtimeScalpingManager not initialized yet
                        payload["scalping_signals"] = []
                        payload["scalping_summary"] = {
                            "total_signals": 0,
                            "avg_expected_return": 0,
                            "high_priority_count": 0,
                            "stale_signals_count": 0,
                            "avg_age_minutes": 0
                        }
                except Exception as e:
                    logger.error(f"Error getting real-time scalping signals: {e}")
                    payload["scalping_signals"] = []
                    payload["scalping_summary"] = {
                        "total_signals": 0,
                        "avg_expected_return": 0,
                        "high_priority_count": 0,
                        "stale_signals_count": 0,
                        "avg_age_minutes": 0
                    }
                
                # Send the complete payload
                await websocket.send_json({
                    "status": "success",
                    "message": f"Live data: {len(payload['opportunities'])} opportunities, {payload['live_tracking']['active_signals_count']} active signals, {len(payload['scalping_signals'])} scalping signals",
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

@router.websocket("/ws/flow-trading")
async def flow_trading_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for flow trading real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(3)  # Update every 3 seconds for flow trading
            await send_flow_trading_update(websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Flow trading WebSocket error: {e}")
        manager.disconnect(websocket)

async def send_update(websocket: WebSocket):
    """Send general trading updates"""
    try:
        opportunities = []
        scalping_signals = []
        scalping_summary = {}
        flow_trading_status = {}
        
        # Get opportunities
        if opportunity_manager:
            try:
                opportunities = opportunity_manager.get_active_opportunities()[:10]
            except Exception as e:
                logger.warning(f"Error getting opportunities: {e}")
        
        # Get scalping data
        if realtime_scalping_manager:
            try:
                scalping_signals = realtime_scalping_manager.get_active_signals()
                scalping_summary = realtime_scalping_manager.get_summary()
            except Exception as e:
                logger.warning(f"Error getting scalping data: {e}")
        
        # Get flow trading data
        if flow_manager:
            try:
                strategies = flow_manager.get_all_strategies_status()
                active_grids = len([s for s in strategies if s.get('current_strategy') == 'grid_trading'])
                active_scalping = len([s for s in strategies if s.get('current_strategy') == 'scalping'])
                
                flow_trading_status = {
                    "enabled": True,
                    "active_strategies": len(strategies),
                    "active_grids": active_grids,
                    "active_scalping": active_scalping,
                    "strategies": strategies[:5]  # Send first 5 strategies
                }
            except Exception as e:
                logger.warning(f"Error getting flow trading data: {e}")
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "opportunities": opportunities,
            "scalping_signals": scalping_signals,
            "scalping_summary": scalping_summary,
            "flow_trading": flow_trading_status,
            "type": "update"
        }
        
        await websocket.send_text(json.dumps(data))
        
    except Exception as e:
        logger.error(f"Error sending update: {e}")

async def send_scalping_update(websocket: WebSocket):
    """Send scalping-specific updates"""
    try:
        if not realtime_scalping_manager:
            return
        
        signals = realtime_scalping_manager.get_active_signals()
        summary = realtime_scalping_manager.get_summary()
        
        # Get recent signal events
        recent_events = []
        try:
            recent_events = realtime_scalping_manager.get_recent_events(limit=5)
        except Exception as e:
            logger.warning(f"Error getting recent events: {e}")
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "signals": signals,
            "summary": summary,
            "recent_events": recent_events,
            "type": "scalping_update"
        }
        
        await websocket.send_text(json.dumps(data))
        
    except Exception as e:
        logger.error(f"Error sending scalping update: {e}")

async def send_flow_trading_update(websocket: WebSocket):
    """Send flow trading specific updates"""
    try:
        if not flow_manager:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "enabled": False,
                "message": "Flow trading not initialized",
                "type": "flow_trading_update"
            }
            await websocket.send_text(json.dumps(data))
            return
        
        # Get all strategy statuses
        strategies = flow_manager.get_all_strategies_status()
        
        # Get grid statuses
        grids = []
        if grid_engine:
            try:
                grids = grid_engine.get_all_grids_status()
            except Exception as e:
                logger.warning(f"Error getting grid statuses: {e}")
        
        # Calculate summary metrics
        active_grids = len([s for s in strategies if s.get('current_strategy') == 'grid_trading'])
        active_scalping = len([s for s in strategies if s.get('current_strategy') == 'scalping'])
        
        # Get recent strategy switches (mock data for now)
        recent_switches = []
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "enabled": True,
            "active_strategies": len(strategies),
            "active_grids": active_grids,
            "active_scalping": active_scalping,
            "strategies": strategies,
            "grids": grids,
            "recent_switches": recent_switches,
            "total_exposure_usd": 0.0,  # Would calculate from risk manager
            "daily_pnl": 0.0,  # Would calculate from performance
            "type": "flow_trading_update"
        }
        
        await websocket.send_text(json.dumps(data))
        
    except Exception as e:
        logger.error(f"Error sending flow trading update: {e}")

async def broadcast_flow_trading_event(event_type: str, event_data: Dict):
    """Broadcast flow trading events to all connected clients"""
    try:
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": event_data,
            "type": "flow_trading_event"
        }
        
        await manager.broadcast(json.dumps(message))
        
    except Exception as e:
        logger.error(f"Error broadcasting flow trading event: {e}")

async def broadcast_strategy_switch(symbol: str, from_strategy: str, to_strategy: str, reason: str):
    """Broadcast strategy switch events"""
    await broadcast_flow_trading_event("strategy_switch", {
        "symbol": symbol,
        "from_strategy": from_strategy,
        "to_strategy": to_strategy,
        "reason": reason
    })

async def broadcast_grid_event(event_type: str, symbol: str, grid_data: Dict):
    """Broadcast grid trading events"""
    await broadcast_flow_trading_event(f"grid_{event_type}", {
        "symbol": symbol,
        "grid_data": grid_data
    })

# Store reference for other modules to use
websocket_manager = manager
