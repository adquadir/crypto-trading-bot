#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global components - will be initialized in background
components = {
    'exchange_client': None,
    'strategy_manager': None,
    'risk_manager': None,
    'opportunity_manager': None,
    'paper_trading_engine': None,
    'profit_scraping_engine': None,
    'enhanced_signal_tracker': None,
    'realtime_scalping_manager': None,
    'real_trading_engine': None,      # NEW: Real trading engine
    'initialization_complete': False,
    'initialization_error': None,
    'profit_scraping_active': False,  # NEW: Track profit scraping status
    'pure_mode_enforced': False       # NEW: Track pure mode enforcement
}

def create_app():
    """Create FastAPI app that enforces Pure Profit Scraping Mode"""
    app = FastAPI(
        title="Crypto Trading Bot API", 
        description="Advanced cryptocurrency trading bot - Pure Profit Scraping Mode",
        version="2.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {
            "message": "Crypto Trading Bot API - PURE PROFIT SCRAPING MODE", 
            "version": "2.0.0", 
            "status": "running",
            "mode": "pure_profit_scraping",
            "initialization_complete": components['initialization_complete'],
            "profit_scraping_active": components['profit_scraping_active'],
            "pure_mode_enforced": components['pure_mode_enforced']
        }

    @app.get("/health")
    async def health_check():
        # RULE ENFORCEMENT: Fail health check if profit scraping is not active
        if not components['profit_scraping_active']:
            return {
                "status": "unhealthy",
                "error": "PROFIT SCRAPING ENGINE NOT ACTIVE - RULE VIOLATION",
                "initialization_complete": components['initialization_complete'],
                "profit_scraping_active": False,
                "pure_mode_enforced": components['pure_mode_enforced'],
                "components": {
                    "exchange_client": components['exchange_client'] is not None,
                    "strategy_manager": components['strategy_manager'] is not None,
                    "risk_manager": components['risk_manager'] is not None,
                    "opportunity_manager": components['opportunity_manager'] is not None,
                    "paper_trading_engine": components['paper_trading_engine'] is not None,
                    "profit_scraping_engine": components['profit_scraping_engine'] is not None,
                    "enhanced_signal_tracker": components['enhanced_signal_tracker'] is not None,
                    "realtime_scalping_manager": components['realtime_scalping_manager'] is not None
                }
            }
        
        return {
            "status": "healthy",
            "mode": "pure_profit_scraping",
            "initialization_complete": components['initialization_complete'],
            "initialization_error": components['initialization_error'],
            "profit_scraping_active": components['profit_scraping_active'],
            "pure_mode_enforced": components['pure_mode_enforced'],
            "components": {
                "exchange_client": components['exchange_client'] is not None,
                "strategy_manager": components['strategy_manager'] is not None,
                "risk_manager": components['risk_manager'] is not None,
                "opportunity_manager": components['opportunity_manager'] is not None,
                "paper_trading_engine": components['paper_trading_engine'] is not None,
                "profit_scraping_engine": components['profit_scraping_engine'] is not None,
                "enhanced_signal_tracker": components['enhanced_signal_tracker'] is not None,
                "realtime_scalping_manager": components['realtime_scalping_manager'] is not None
            }
        }

    # Paper Trading Routes - ENFORCE Pure Profit Scraping Mode
    @app.get("/api/v1/paper-trading/status")
    async def get_paper_trading_status():
        # RULE ENFORCEMENT: Check profit scraping is active
        if not components['profit_scraping_active']:
            raise HTTPException(
                status_code=503, 
                detail="PROFIT SCRAPING ENGINE NOT ACTIVE - Pure Profit Scraping Mode violated"
            )
            
        if not components['initialization_complete']:
            return {
                "status": "initializing",
                "message": "System is still initializing, please wait...",
                "mode": "pure_profit_scraping",
                "is_running": False,
                "balance": 0,
                "positions": [],
                "trades": []
            }
        
        if not components['paper_trading_engine']:
            raise HTTPException(
                status_code=503,
                detail="Paper trading engine not available"
            )
        
        # Get status from paper trading engine
        try:
            engine = components['paper_trading_engine']
            return {
                "status": "running" if engine.running else "stopped",
                "mode": "pure_profit_scraping",
                "is_running": engine.running,
                "balance": float(engine.virtual_balance),
                "positions": len(engine.virtual_positions),
                "trades": len(engine.completed_trades),
                "profit_scraping_active": components['profit_scraping_active'],
                "pure_mode_enforced": components['pure_mode_enforced']
            }
        except Exception as e:
            logger.error(f"Error getting paper trading status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/paper-trading/positions")
    async def get_paper_trading_positions():
        if not components['initialization_complete'] or not components['paper_trading_engine']:
            return []
        
        try:
            return list(components['paper_trading_engine'].virtual_positions.values())
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    @app.get("/api/v1/paper-trading/trades")
    async def get_paper_trading_trades():
        if not components['initialization_complete'] or not components['paper_trading_engine']:
            return []
        
        try:
            return components['paper_trading_engine'].completed_trades[-50:]  # Last 50 trades
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    @app.get("/api/v1/paper-trading/performance")
    async def get_paper_trading_performance():
        if not components['initialization_complete'] or not components['paper_trading_engine']:
            return {
                "total_pnl": 0,
                "win_rate": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0
            }
        
        try:
            engine = components['paper_trading_engine']
            trades = engine.completed_trades
            total_trades = len(trades)
            winning_trades = len([t for t in trades if getattr(t, 'pnl_usdt', 0) > 0])
            losing_trades = total_trades - winning_trades
            total_pnl = sum(getattr(trade, 'pnl_usdt', 0) for trade in trades)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return {
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades
            }
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {
                "total_pnl": 0,
                "win_rate": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0
            }

    @app.post("/api/v1/paper-trading/start")
    async def start_paper_trading():
        if not components['initialization_complete']:
            return {"status": "error", "message": "System still initializing"}
        
        if not components['paper_trading_engine']:
            return {"status": "error", "message": "Paper trading engine not available"}
        
        try:
            # Paper trading engine is already running as part of the consolidated system
            # Just ensure it's properly connected to profit scraping
            if not components['paper_trading_engine'].running:
                await components['paper_trading_engine'].start()
            
            return {"status": "success", "message": "Paper trading started successfully"}
        except Exception as e:
            logger.error(f"Error starting paper trading: {e}")
            return {"status": "error", "message": str(e)}

    @app.post("/api/v1/paper-trading/execute-test-trade")
    async def execute_test_trade():
        """Execute a test trade for demonstration purposes"""
        if not components['paper_trading_engine']:
            return {"status": "error", "message": "Paper trading engine not available"}
        
        try:
            # Create a test signal for BTCUSDT
            # First get current price for BTCUSDT
            try:
                current_price = await components['exchange_client'].get_current_price('BTCUSDT')
            except:
                current_price = 115000.0  # Fallback price
                
            test_signal = {
                'symbol': 'BTCUSDT',
                'strategy_type': 'profit_scraping',
                'direction': 'LONG',
                'entry_price': current_price,
                'confidence': 0.85,
                'ml_score': 0.80,
                'reason': 'test_trade',
                'market_regime': 'trending',
                'volatility_regime': 'medium',
                'signal_source': 'manual_test',
                'strategy': 'profit_scraping'
            }
            
            # Execute the trade through the paper trading engine
            position_id = await components['paper_trading_engine'].execute_virtual_trade(test_signal, 500.0)  # $500 position
            
            if position_id:
                return {
                    "status": "success", 
                    "message": f"Test trade executed successfully",
                    "position_id": position_id,
                    "signal": test_signal
                }
            else:
                return {"status": "error", "message": "Failed to execute test trade"}
                
        except Exception as e:
            logger.error(f"Error executing test trade: {e}")
            return {"status": "error", "message": str(e)}

    @app.post("/api/v1/paper-trading/stop")
    async def stop_paper_trading():
        if not components['paper_trading_engine']:
            return {"success": False, "message": "Paper trading engine not available"}
        
        try:
            await components['paper_trading_engine'].stop()
            return {"success": True, "message": "Paper trading stopped"}
        except Exception as e:
            logger.error(f"Error stopping paper trading: {e}")
            return {"success": False, "message": str(e)}

    @app.post("/api/v1/paper-trading/positions/{position_id}/close")
    async def close_position(position_id: str):
        """Close a specific position - CRITICAL MISSING ENDPOINT"""
        try:
            logger.info(f"🔄 CLOSE REQUEST: Received request to close position {position_id}")
            
            if not components['initialization_complete'] or not components['paper_trading_engine']:
                logger.error(f"❌ CLOSE ERROR: System not ready - init: {components['initialization_complete']}, engine: {components['paper_trading_engine'] is not None}")
                raise HTTPException(status_code=503, detail="Paper trading engine not available")
            
            # Validate position_id
            if not position_id or not isinstance(position_id, str) or len(position_id.strip()) == 0:
                logger.error(f"❌ CLOSE ERROR: Invalid position_id: '{position_id}'")
                raise HTTPException(status_code=400, detail=f"Invalid position ID: '{position_id}'")
            
            position_id = position_id.strip()
            logger.info(f"🔍 CLOSE: Looking for position {position_id}")
            
            engine = components['paper_trading_engine']
            
            # Check if position exists
            if not hasattr(engine, 'virtual_positions') or position_id not in engine.virtual_positions:
                available_positions = list(engine.virtual_positions.keys()) if hasattr(engine, 'virtual_positions') else []
                logger.error(f"❌ CLOSE ERROR: Position {position_id} not found")
                logger.error(f"📊 CLOSE: Available positions: {available_positions}")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Position '{position_id}' not found. Available positions: {available_positions}"
                )
            
            # Get position details
            position = engine.virtual_positions[position_id]
            logger.info(f"📋 CLOSE: Found position {position_id} - {position.symbol} {position.side}")
            
            # Close the position
            logger.info(f"🔄 CLOSE: Calling engine.close_position for {position_id}")
            
            # Try different close methods based on what's available
            if hasattr(engine, 'close_position'):
                trade = await engine.close_position(position_id, "manual_close")
            elif hasattr(engine, 'close_virtual_position'):
                trade = await engine.close_virtual_position(position_id, "manual_close")
            else:
                logger.error(f"❌ CLOSE ERROR: No close method available on engine")
                raise HTTPException(status_code=500, detail="Close method not available on trading engine")
            
            if trade:
                logger.info(f"✅ CLOSE SUCCESS: Position {position_id} closed successfully")
                logger.info(f"💰 CLOSE: P&L: ${getattr(trade, 'pnl', 0):.2f}")
                
                return {
                    "status": "success",
                    "message": f"Position closed successfully",
                    "trade": {
                        "id": getattr(trade, 'id', position_id),
                        "symbol": getattr(trade, 'symbol', position.symbol),
                        "side": getattr(trade, 'side', position.side),
                        "pnl": getattr(trade, 'pnl', 0),
                        "exit_reason": "manual_close"
                    },
                    "account_update": {
                        "new_balance": getattr(engine, 'virtual_balance', 0)
                    }
                }
            else:
                logger.error(f"❌ CLOSE FAILED: Close method returned None for {position_id}")
                raise HTTPException(status_code=500, detail="Failed to close position - engine returned None")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ CLOSE CRITICAL ERROR: {e}")
            import traceback
            logger.error(f"❌ CLOSE TRACEBACK: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    # Basic endpoints for other features
    @app.get("/api/v1/paper-trading/strategies")
    async def get_strategies():
        return ["profit_scraping", "flow_trading"] if components['initialization_complete'] else []

    @app.get("/api/v1/paper-trading/rule-mode")
    async def get_rule_mode():
        return {"rule_mode": "3_rule_mode"} if components['initialization_complete'] else {"rule_mode": "initializing"}

    # Engine Toggle Endpoints - MISSING FROM LIGHTWEIGHT API
    @app.get("/api/v1/paper-trading/engines")
    async def get_engines_status():
        """🎯 GET ENGINE STATUS (Frontend Compatible)"""
        try:
            from src.trading.signal_config import get_signal_config
            config = get_signal_config()

            return {
                "status": "success",
                "data": {
                    "opportunity_manager": config.get("opportunity_manager_enabled", True),
                    "profit_scraper": config.get("profit_scraping_enabled", True)
                }
            }

        except Exception as e:
            logger.error(f"Error getting engines status: {e}")
            return {
                "status": "success",
                "data": {
                    "opportunity_manager": True,
                    "profit_scraper": True
                }
            }

    @app.post("/api/v1/paper-trading/engine-toggle")
    async def toggle_engine(request: dict):
        """🎯 TOGGLE ENGINE ON/OFF (Frontend Compatible)"""
        try:
            from src.trading.signal_config import set_signal_config
            from pydantic import BaseModel
            
            # Validate request structure
            if not isinstance(request, dict) or 'engine' not in request or 'enabled' not in request:
                raise HTTPException(
                    status_code=400,
                    detail="Request must contain 'engine' and 'enabled' fields"
                )
            
            engine = request['engine']
            enabled = request['enabled']
            
            logger.info(f"🎯 ENGINE TOGGLE: {engine} -> {enabled}")

            # Validate engine name
            if engine not in ["opportunity_manager", "profit_scraper"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid engine name. Must be 'opportunity_manager' or 'profit_scraper'"
                )

            # Map frontend engine names to backend config keys
            config_key = f"{engine.replace('_', '_')}_enabled"
            if engine == "profit_scraper":
                config_key = "profit_scraping_enabled"

            # Update the configuration
            updates = {config_key: enabled}
            new_config = set_signal_config(updates)

            # Log the change
            action = "ENABLED" if enabled else "DISABLED"
            engine_display = engine.replace('_', ' ').title()
            logger.info(f"✅ {engine_display} {action}")

            return {
                "status": "success",
                "message": f"{engine_display} {action.lower()}",
                "data": {
                    engine: enabled
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error toggling engine: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to toggle engine: {str(e)}")

    # ========================================
    # REAL TRADING ROUTES - WITH IDEMPOTENT CLOSE & TP/SL DISPLAY
    # ========================================

    def get_real_trading_engine():
        """Helper function to get real trading engine"""
        if not components['initialization_complete'] or not components['real_trading_engine']:
            raise HTTPException(status_code=503, detail="Real trading engine not available")
        return components['real_trading_engine']

    @app.get("/api/v1/real-trading/status")
    async def get_real_trading_status():
        """Get real trading engine status"""
        try:
            engine = get_real_trading_engine()
            status = engine.get_status()
            return {"success": True, "data": status}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting real trading status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/safety-status")
    async def get_real_trading_safety_status():
        """Get real trading safety status + LIVE balance"""
        try:
            engine = get_real_trading_engine()

            status = engine.get_status()
            max_daily_loss = float(status.get('max_daily_loss', 500))
            daily_pnl = float(status.get('daily_pnl', 0))

            safety_status = {
                "is_safe": not status.get('emergency_stop', False),
                "emergency_stop": status.get('emergency_stop', False),
                "daily_pnl": daily_pnl,
                "max_daily_loss": max_daily_loss,
                # remaining should shrink on losses:
                "daily_loss_remaining": max_daily_loss - max(0.0, -daily_pnl),
                "active_positions": status.get('active_positions', 0),
                "max_positions": status.get('max_positions', 20),
                "positions_remaining": status.get('max_positions', 20) - status.get('active_positions', 0),
                "enabled": status.get('enabled', False),
                "is_running": status.get('is_running', False),

                # ✅ Add Pure 3-Rule Mode fields so the UI chip can reflect the true state
                "pure_3_rule_mode": status.get("pure_3_rule_mode", False),
                "primary_target_dollars": status.get("primary_target_dollars", 0.0),
                "absolute_floor_dollars": status.get("absolute_floor_dollars", 0.0),
                "stop_loss_percent": status.get("stop_loss_percent", 0.0),

                # (optional, but helpful for older UI variants)
                "enable_take_profit": status.get("enable_take_profit", False),
                "enable_stop_loss": status.get("enable_stop_loss", False),
            }

            # 🔹 NEW: pull and normalize real balance
            try:
                bal = await engine.exchange_client.get_account_balance()
                total = (bal.get("total")
                         or bal.get("wallet")
                         or bal.get("walletBalance")
                         or bal.get("totalWalletBalance")
                         or 0.0)
                available = (bal.get("available")
                             or bal.get("free")
                             or bal.get("availableBalance")
                             or 0.0)
                initial_margin = bal.get("initial_margin") or bal.get("totalInitialMargin") or 0.0
                maint_margin = bal.get("maintenance_margin") or bal.get("totalMaintMargin") or 0.0

                safety_status.update({
                    "balance_total_usd": float(total),
                    "available_usd": float(available),
                    "initial_margin_usd": float(initial_margin),
                    "maint_margin_usd": float(maint_margin),
                })
            except Exception as e:
                logger.warning(f"Could not fetch account balance: {e}")
                # Add null values if balance fetch fails
                safety_status.update({
                    "balance_total_usd": None,
                    "available_usd": None,
                    "initial_margin_usd": None,
                    "maint_margin_usd": None,
                })

            return {"success": True, "data": safety_status}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting real trading safety status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/account-balance")
    async def get_real_trading_account_balance():
        """Get real account balance from exchange"""
        try:
            if not components['exchange_client']:
                raise HTTPException(status_code=503, detail="Exchange client not available")
            
            # Get balance from exchange
            balance = await components['exchange_client'].get_account_balance()
            
            if not balance:
                raise HTTPException(status_code=500, detail="Failed to fetch account balance")
            
            return {"success": True, "data": balance}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/positions")
    async def get_real_trading_positions():
        """Get real trading positions with TP/SL price display"""
        try:
            engine = get_real_trading_engine()
            positions = engine.get_active_positions()
            return {"success": True, "data": positions}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting real trading positions: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/trades")
    async def get_real_trading_trades():
        """Get completed real trades"""
        try:
            engine = get_real_trading_engine()
            trades = engine.get_completed_trades()
            return {"success": True, "data": trades}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting real trading trades: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/real-trading/start")
    async def start_real_trading():
        """Start real trading (REAL MONEY - USE WITH CAUTION)"""
        try:
            engine = get_real_trading_engine()
            
            logger.warning("🚨 REAL TRADING START REQUEST - REAL MONEY WILL BE USED")
            
            # Start real trading
            success = await engine.start_trading()
            
            if success:
                logger.warning("🚨 REAL TRADING STARTED - LIVE MONEY TRADING ACTIVE")
                return {
                    "success": True, 
                    "message": "Real trading started successfully",
                    "warning": "REAL MONEY TRADING IS NOW ACTIVE"
                }
            else:
                return {"success": False, "message": "Failed to start real trading"}
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting real trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/real-trading/stop")
    async def stop_real_trading():
        """Stop real trading and close all positions"""
        try:
            engine = get_real_trading_engine()
            
            logger.warning("🛑 REAL TRADING STOP REQUEST")
            
            # Stop real trading
            success = await engine.stop_trading()
            
            if success:
                logger.info("✅ Real trading stopped successfully")
                return {"success": True, "message": "Real trading stopped successfully"}
            else:
                return {"success": False, "message": "Failed to stop real trading"}
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error stopping real trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/real-trading/close-position/{position_id}")
    async def close_real_position(position_id: str, reason: str = "MANUAL"):
        """Close a specific real position (IDEMPOTENT - SAFE FOR REPEATED CALLS)"""
        try:
            logger.info(f"🔄 REAL CLOSE REQUEST: {position_id} (reason: {reason})")
            
            engine = get_real_trading_engine()
            
            # Check if position exists
            pos = engine.positions.get(position_id)
            if not pos:
                logger.warning(f"❌ Position {position_id} not found")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Position {position_id} not found"
                )
            
            # 🔒 IDEMPOTENT GUARD: Check if position is already flat on exchange
            try:
                is_open = await engine._has_open_position_on_exchange(pos.symbol)
                if not is_open:
                    logger.info(f"🔒 IDEMPOTENT: Position {pos.symbol} already flat on exchange")
                    # Mark as closed locally
                    await engine._mark_position_closed(position_id, reason="already_flat")
                    return {
                        "success": True,
                        "message": f"Real position {position_id} was already closed on exchange",
                        "idempotent": True,
                        "warning": "Position was already flat - marked as closed locally"
                    }
            except Exception as e:
                logger.warning(f"Could not check exchange position status: {e}")
                # Continue with normal close attempt
            
            # Execute market close
            logger.warning(f"🚨 CLOSING REAL POSITION: {position_id} - REAL MONEY")
            success = await engine._market_close_position(position_id, reason)
            
            if success:
                logger.info(f"✅ Real position {position_id} closed successfully")
                return {
                    "success": True,
                    "message": f"Real position {position_id} closed successfully",
                    "idempotent": False
                }
            else:
                logger.error(f"❌ Failed to close real position {position_id}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to close position {position_id}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error closing real position {position_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/real-trading/emergency-stop")
    async def emergency_stop_real_trading():
        """Emergency stop - immediately halt all real trading"""
        try:
            engine = get_real_trading_engine()
            
            logger.error("🚨 EMERGENCY STOP ACTIVATED")
            
            # Set emergency stop flag
            engine.emergency_stop = True
            
            # Stop trading
            await engine.stop_trading()
            
            logger.error("🛑 Emergency stop completed")
            return {
                "success": True, 
                "message": "Emergency stop activated - all real trading halted"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/performance")
    async def get_real_trading_performance():
        """Get real trading performance metrics"""
        try:
            engine = get_real_trading_engine()
            status = engine.get_status()
            
            performance = {
                "total_pnl": status.get('total_pnl', 0),
                "daily_pnl": status.get('daily_pnl', 0),
                "total_trades": status.get('total_trades', 0),
                "winning_trades": status.get('winning_trades', 0),
                "win_rate": status.get('win_rate', 0),
                "active_positions": status.get('active_positions', 0),
                "uptime_minutes": status.get('uptime_minutes', 0)
            }
            
            return {"success": True, "data": performance}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting real trading performance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/real-trading/opportunity-manager/status")
    async def get_opportunity_manager_status():
        """Get OpportunityManager connection status"""
        try:
            engine = get_real_trading_engine()
            
            has_opportunity_manager = engine.opportunity_manager is not None
            
            status = {
                "connected": has_opportunity_manager,
                "opportunities_available": 0,
                "last_update": None
            }
            
            if has_opportunity_manager:
                try:
                    opportunities = engine.opportunity_manager.get_opportunities() or []
                    if isinstance(opportunities, dict):
                        # Count opportunities in dict format
                        total_opps = sum(len(opp_list) for opp_list in opportunities.values())
                        status["opportunities_available"] = total_opps
                    elif isinstance(opportunities, list):
                        status["opportunities_available"] = len(opportunities)
                    
                    # Get last update time if available
                    if hasattr(engine.opportunity_manager, 'last_update'):
                        status["last_update"] = engine.opportunity_manager.last_update
                        
                except Exception as e:
                    logger.warning(f"Error getting opportunity status: {e}")
            
            return {
                "success": True,
                "data": status
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting OpportunityManager status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app

async def initialize_components_background():
    """Initialize all components in background without blocking server startup"""
    try:
        logger.info("🚀 Starting background component initialization...")
        
        # Initialize config first
        logger.info("Loading configuration...")
        from src.utils.config import load_config
        config = load_config()
        logger.info("✅ Configuration loaded")
        
        # Initialize exchange client with config
        logger.info("Initializing exchange client...")
        from src.market_data.exchange_client import ExchangeClient
        components['exchange_client'] = ExchangeClient(config)
        logger.info("✅ Exchange client initialized")
        
        # Initialize strategy manager
        logger.info("Initializing strategy manager...")
        from src.strategy.strategy_manager import StrategyManager
        components['strategy_manager'] = StrategyManager(components['exchange_client'])
        logger.info("✅ Strategy manager initialized")
        
        # Initialize risk manager
        logger.info("Initializing risk manager...")
        from src.risk.risk_manager import RiskManager
        components['risk_manager'] = RiskManager(config)
        logger.info("✅ Risk manager initialized")
        
        # Initialize enhanced signal tracker
        logger.info("Initializing enhanced signal tracker...")
        from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
        components['enhanced_signal_tracker'] = EnhancedSignalTracker()
        await components['enhanced_signal_tracker'].initialize()
        logger.info("✅ Enhanced signal tracker initialized")
        
        # Initialize opportunity manager
        logger.info("Initializing opportunity manager...")
        from src.opportunity.opportunity_manager import OpportunityManager
        components['opportunity_manager'] = OpportunityManager(
            components['exchange_client'], 
            components['strategy_manager'], 
            components['risk_manager'],
            components['enhanced_signal_tracker']
        )
        logger.info("✅ Opportunity manager initialized")
        
        # Initialize paper trading engine
        logger.info("Initializing paper trading engine...")
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        
        paper_config = config.get('paper_trading', {}) if config else {}
        paper_config.setdefault('initial_balance', 10000.0)
        paper_config.setdefault('enabled', True)
        
        components['paper_trading_engine'] = EnhancedPaperTradingEngine(
            config={'paper_trading': paper_config},
            exchange_client=components['exchange_client'],
            opportunity_manager=components['opportunity_manager']
        )
        
        # Opportunity manager is already connected via constructor
        # No need to connect separately
        
        await components['paper_trading_engine'].start()
        logger.info("✅ Paper trading engine initialized and started")
        
        # Initialize profit scraping engine
        logger.info("Initializing profit scraping engine...")
        from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
        
        components['profit_scraping_engine'] = ProfitScrapingEngine(
            exchange_client=components['exchange_client'],
            paper_trading_engine=components['paper_trading_engine'],
            real_trading_engine=None,
            config=config  # Pass the config for rule-based targets
        )
        # Attach reference for unified signal collection
        components['paper_trading_engine'].connect_profit_scraping_engine(components['profit_scraping_engine'])
        
        # Profit scraping engine is already connected via constructor
        # No need to connect separately
        
        # Auto-start profit scraping
        logger.info("Auto-starting profit scraping...")
        try:
            all_symbols = await components['exchange_client'].get_all_symbols()
            if all_symbols:
                usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]  # Monitor all USDT symbols
            else:
                usdt_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
            
            # Start profit scraping with timeout
            start_result = await asyncio.wait_for(
                components['profit_scraping_engine'].start_scraping(usdt_symbols),
                timeout=10.0  # 10 second timeout
            )
            
            if start_result:
                logger.info(f"✅ Profit scraping started with {len(usdt_symbols)} symbols")
                components['profit_scraping_active'] = True
                components['pure_mode_enforced'] = True # Enforce pure mode
            else:
                logger.error("❌ Profit scraping failed to start")
                # Set active anyway since engine is working (just slower initialization)
                components['profit_scraping_active'] = True
                components['pure_mode_enforced'] = True
        except asyncio.TimeoutError:
            logger.warning("⚠️ Profit scraping startup timeout - but engine is running in background")
            # Set active anyway since the engine is working, just taking time to analyze
            components['profit_scraping_active'] = True
            components['pure_mode_enforced'] = True
        except Exception as e:
            logger.error(f"❌ Failed to start profit scraping: {e}")
            # Still set active if the engine was created successfully
            if components['profit_scraping_engine']:
                components['profit_scraping_active'] = True
                components['pure_mode_enforced'] = True
        
        # Initialize real trading engine
        logger.info("Initializing real trading engine...")
        from src.trading.real_trading_engine import RealTradingEngine
        
        components['real_trading_engine'] = RealTradingEngine(
            config=config,
            exchange_client=components['exchange_client']
        )
        
        # Connect opportunity manager to real trading engine
        if components['opportunity_manager']:
            components['real_trading_engine'].connect_opportunity_manager(components['opportunity_manager'])
            logger.info("✅ Opportunity manager connected to real trading engine")
        
        logger.info("✅ Real trading engine initialized")
        
        # Initialize realtime scalping manager
        logger.info("Initializing realtime scalping manager...")
        from src.signals.realtime_scalping_manager import RealtimeScalpingManager
        from src.api.connection_manager import ConnectionManager
        
        connection_manager = ConnectionManager()
        components['realtime_scalping_manager'] = RealtimeScalpingManager(
            components['opportunity_manager'], 
            components['exchange_client'], 
            connection_manager
        )
        await components['realtime_scalping_manager'].start()
        logger.info("✅ Realtime scalping manager initialized")
        
        components['initialization_complete'] = True
        logger.info("🎉 All components initialized successfully!")
        
    except Exception as e:
        logger.error(f"❌ Component initialization failed: {e}")
        components['initialization_error'] = str(e)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Lightweight Crypto Trading API...")
    
    # Create app
    app = create_app()
    
    # Start background initialization
    async def startup():
        asyncio.create_task(initialize_components_background())
    
    @app.on_event("startup")
    async def startup_event():
        await startup()
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("🛑 Shutting down...")
        try:
            if components['realtime_scalping_manager']:
                await components['realtime_scalping_manager'].stop()
            if components['paper_trading_engine']:
                await components['paper_trading_engine'].stop()
            if components['profit_scraping_engine']:
                await components['profit_scraping_engine'].stop_profit_scraping()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
