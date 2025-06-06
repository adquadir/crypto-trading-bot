from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
import json
import asyncio
from datetime import datetime
import logging
import traceback
import os
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity
from src.signals.signal_generator import SignalGenerator
from src.config import EXCHANGE_CONFIG
from src.database.models import Trade
from src.database.database import SessionLocal
from sqlalchemy.orm import Session
import numpy as np

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crypto Trading Bot API",
    description="API for the Crypto Trading Bot Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://50.31.0.105:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize exchange client
exchange_client = ExchangeClient(
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=os.getenv('USE_TESTNET', 'False').lower() == 'true'
)

# Initialize symbol discovery
symbol_discovery = SymbolDiscovery(exchange_client)

# Initialize signal generator
signal_generator = SignalGenerator()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections[client_id])}")
        
    async def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            if websocket in self.active_connections[client_id]:
                self.active_connections[client_id].remove(websocket)
                logger.info(f"Client {client_id} disconnected. Remaining connections: {len(self.active_connections[client_id])}")
            
            # Clean up empty client lists
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
                if client_id in self.connection_tasks:
                    self.connection_tasks[client_id].cancel()
                    try:
                        await self.connection_tasks[client_id]
                    except asyncio.CancelledError:
                        pass
                    del self.connection_tasks[client_id]
                    
    async def broadcast(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[client_id]:
                try:
                    if connection.client_state.CONNECTED:  # Check if still connected
                        await connection.send_json(message)
                    else:
                        disconnected.append(connection)
                except Exception as e:
                    logger.error(f"Error broadcasting to client {client_id}: {e}")
                    disconnected.append(connection)
                    
            # Clean up disconnected websockets
            for connection in disconnected:
                await self.disconnect(connection, client_id)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    await exchange_client.initialize()
    # Start symbol discovery scan on startup
    asyncio.create_task(symbol_discovery.scan_opportunities())
    logger.info("API server started")

@app.on_event("shutdown")
async def shutdown_event():
    # Cancel all connection tasks
    for task in manager.connection_tasks.values():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Close all websocket connections
    for client_id, connections in list(manager.active_connections.items()):
        for connection in connections:
            try:
                await connection.close()
            except Exception as e:
                logger.error(f"Error closing websocket for client {client_id}: {e}")
    
    # Clear all connection data
    manager.active_connections.clear()
    manager.connection_tasks.clear()
    
    # Close exchange client
    await exchange_client.close()
    logger.info("API server shutdown complete")

async def market_data_stream(client_id: str):
    """Stream market data to connected clients."""
    try:
        while True:
            # Get symbols from dynamically discovered opportunities
            # Trigger a scan to ensure opportunities are up-to-date before streaming
            opportunities_list = await symbol_discovery.scan_opportunities()
            symbols_to_stream = [opp.symbol for opp in opportunities_list]

            if not symbols_to_stream:
                logger.warning("No active opportunities to stream market data.")
                await asyncio.sleep(10) # Wait before checking again
                continue

            for symbol in symbols_to_stream:
                try:
                    # Get market data
                    market_data = await symbol_discovery.get_market_data(symbol)
                    if not market_data:
                        continue
                        
                    # Generate signals
                    # The signal_generator expects a pandas DataFrame, but market_data is a dict
                    # Need to pass the relevant parts or refactor signal generation input
                    # For now, skipping signal generation in stream to avoid errors
                    # signal = signal_generator.generate_signals(symbol, market_data, 1.0) # Assuming 1.0 confidence for stream for now
                    signal = None # Temporarily disable signal generation in stream

                    # Prepare message
                    message = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': symbol,
                        'market_data': market_data,
                        'signal': signal # Signal will be None for now
                    }
                    
                    # Broadcast to client
                    await manager.broadcast(message, client_id)
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)  # 1 second delay between symbols
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol} in market data stream: {e}")
                    continue
                    
            # Wait before next update cycle
            await asyncio.sleep(5.0)  # 5 second delay between cycles
            
    except asyncio.CancelledError:
        logger.info(f"Market data stream cancelled for client {client_id}")
    except Exception as e:
        logger.error(f"Market data stream error for client {client_id}: {e}")
    finally:
        # Clean up any remaining connections for this client
        if client_id in manager.active_connections:
            for connection in manager.active_connections[client_id]:
                try:
                    await connection.close()
                except Exception as e:
                    logger.error(f"Error closing websocket for client {client_id}: {e}")
            del manager.active_connections[client_id]

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        await manager.connect(websocket, client_id)
        
        # Start market data stream if not already running
        if client_id not in manager.connection_tasks:
            manager.connection_tasks[client_id] = asyncio.create_task(
                market_data_stream(client_id)
            )
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages here if needed
            except WebSocketDisconnect:
                await manager.disconnect(websocket, client_id)
                break
            except Exception as e:
                logger.error(f"WebSocket error for client {client_id}: {e}")
                await manager.disconnect(websocket, client_id)
                break
                
    except Exception as e:
        logger.error(f"Error in websocket endpoint for client {client_id}: {e}")
        await manager.disconnect(websocket, client_id)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/symbols")
async def get_symbols():
    """Get list of available trading symbols."""
    # Return symbols from dynamically discovered opportunities
    # Trigger a scan to ensure symbols are up-to-date
    opportunities_list = await symbol_discovery.scan_opportunities()
    symbols_list = [opp.symbol for opp in opportunities_list]
    return {"symbols": symbols_list}

def clean_float_values(data):
    """Recursively replace NaN and Infinity float values with None."""
    if isinstance(data, float):
        if np.isnan(data) or np.isinf(data):
            return None
        return data
    elif isinstance(data, dict):
        return {k: clean_float_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_float_values(item) for item in data]
    elif hasattr(data, '__dict__'):
        # Handle objects by converting to dict and cleaning
        return clean_float_values(data.__dict__)
    else:
        return data

@app.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get current market data for a symbol."""
    # Validate symbol against dynamically discovered opportunities
    # Trigger a scan to ensure valid symbols are up-to-date
    opportunities_list = await symbol_discovery.scan_opportunities()
    valid_symbols = [opp.symbol for opp in opportunities_list]

    if symbol not in valid_symbols:
        # If not in current opportunities, check if it's a generally tradable symbol
        # This requires fetching exchange info again or having a cached list
        # For simplicity now, just check against scanned opportunities
        # A more robust solution would check all exchange symbols or a recent cache
        logger.warning(f"Requested symbol {symbol} not in current opportunities. Validation failed.")
        raise HTTPException(status_code=400, detail="Invalid or inactive symbol")

    try:
        market_data = await exchange_client.get_market_data(symbol)
        if not market_data:
            raise HTTPException(status_code=404, detail="Market data not available")
        
        # Apply filtering
        filtered_market_data = {
            'risk_reward_ratio': market_data.get('risk_reward_ratio'),
            'volatility_score': market_data.get('volatility_score'),
            'technical_score': market_data.get('technical_score'),
            'fundamental_score': market_data.get('fundamental_score'),
            'overall_score': market_data.get('overall_score'),
            'signal_strength': market_data.get('signal_strength'),
            'signal_type': market_data.get('signal_type'),
            'entry_price': market_data.get('entry_price'),
            'take_profit': market_data.get('take_profit'),
            'stop_loss': market_data.get('stop_loss')
        }

        # Clean potential NaN/Infinity values before returning
        cleaned_market_data = clean_float_values(filtered_market_data)

        return JSONResponse(content=cleaned_market_data)
    except Exception as e:
        logger.error(f"Error fetching market data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# REST endpoints
@app.get("/api/trading/signals")
async def get_signals():
    return {
        "signals": [
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": "BTCUSDT",
                "signal": "BUY",
                "confidence": 0.85,
                "indicators": {
                    "macd": {"value": 0.5, "signal": 0.3},
                    "rsi": 65,
                    "bb": {"upper": 50000, "middle": 48000, "lower": 46000}
                }
            }
        ]
    }

@app.get("/api/trading/pnl")
async def get_pnl():
    return {
        "total_pnl": 1234.56,
        "daily_pnl": 234.56,
        "win_rate": 0.65,
        "trades": [
            {
                "symbol": "BTCUSDT",
                "entry_price": 48000,
                "exit_price": 49000,
                "pnl": 1000,
                "timestamp": datetime.now().isoformat()
            }
        ]
    }

@app.get("/api/trading/stats")
async def get_stats():
    """Get trading statistics including profile performance and parameter history."""
    db: Session = SessionLocal()
    try:
        # Get all closed trades from the database
        trades = db.query(Trade).filter(Trade.status == 'CLOSED').all()

        # Calculate total trades
        total_trades = len(trades)

        # Calculate win rate and total PnL
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        total_pnl = sum(t.pnl for t in trades if t.pnl is not None)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        # Calculate profit factor
        total_profit = sum(t.pnl for t in trades if t.pnl and t.pnl > 0)
        total_loss = abs(sum(t.pnl for t in trades if t.pnl and t.pnl < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # Calculate maximum drawdown (simplified - needs proper implementation)
        # This is a placeholder; a full drawdown calculation requires tracking equity over time.
        max_drawdown = 0.0 # Placeholder

        # Placeholder for other metrics that are not directly available from Trade model or need aggregation
        daily_risk_usage = {} # Needs logic to aggregate risk usage per day
        current_leverage = {} # Needs logic to get current positions and their leverage
        portfolio_beta = 0.0 # Needs portfolio historical data and benchmark data
        profile_performance = {} # Needs aggregation based on trades associated with profiles (if stored)
        parameter_history = [] # Needs to be stored by the bot
        volatility_impact = {} # Needs analysis within the bot

        # Note: Metrics like daily_risk_usage, current_leverage, portfolio_beta,
        # profile_performance, parameter_history, and volatility_impact are best calculated
        # and potentially stored by the TradingBot process itself, as it has the necessary context.
        # This API endpoint provides basic trade history based stats for now.

        stats = {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown, # Placeholder
            "daily_risk_usage": daily_risk_usage, # Placeholder
            "current_leverage": current_leverage, # Placeholder
            # These would ideally come from stored data or a dedicated stats table updated by the bot
            "profile_performance": {}, # Placeholder
            "parameter_history": [], # Placeholder
            "volatility_impact": {} # Placeholder
        }
        return {"stats": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/trading/positions")
async def get_positions():
    return {
        "positions": [
            {
                "symbol": "BTCUSDT",
                "size": 0.1,
                "entry_price": 48000,
                "current_price": 49000,
                "pnl": 100,
                "leverage": 3
            }
        ]
    }

@app.get("/api/trading/strategies")
async def get_strategies():
    return {
        "strategies": [
            {
                "name": "MACD Crossover",
                "active": True,
                "performance": {
                    "win_rate": 0.65,
                    "profit_factor": 1.89,
                    "sharpe_ratio": 1.5
                }
            }
        ]
    }

@app.get("/api/trading/settings")
async def get_settings():
    return {
        "maxPositionSize": 0.1,
        "maxLeverage": 3.0,
        "riskPerTrade": 0.02,
        "maxOpenTrades": 5,
        "maxCorrelation": 0.7,
        "minRiskReward": 2.0,
        "maxDailyLoss": 0.05,
        "maxDrawdown": 0.15
    }

@app.post("/api/trading/settings")
async def update_settings(settings: dict):
    # In a real implementation, you would save these settings
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/trading/opportunities")
async def get_opportunities(
    min_confidence: float = 0.7,
    min_risk_reward: float = 2.0,
    min_volume: float = 1000000,
    limit: int = 10
):
    """Get top trading opportunities."""
    try:
        opportunities = await symbol_discovery.scan_opportunities()
        
        # Filter opportunities
        filtered = [
            opp for opp in opportunities
            if opp.confidence >= min_confidence
            and opp.risk_reward >= min_risk_reward
            and opp.volume_24h >= min_volume
        ]
        
        # Sort by score and limit
        filtered.sort(key=lambda x: x.score, reverse=True)
        top_opportunities = filtered[:limit]
        
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "opportunities_update",
            "data": {
                "opportunities": [
                    {
                        "symbol": opp.symbol,
                        "direction": opp.direction,
                        "entry_price": opp.entry_price,
                        "take_profit": opp.take_profit,
                        "stop_loss": opp.stop_loss,
                        "confidence": opp.confidence,
                        "leverage": opp.leverage,
                        "risk_reward": opp.risk_reward,
                        "volume_24h": opp.volume_24h,
                        "volatility": opp.volatility,
                        "score": opp.score,
                        "indicators": opp.indicators,
                        "reasoning": opp.reasoning
                    }
                    for opp in top_opportunities
                ],
                "total": len(filtered),
                "timestamp": datetime.now().timestamp()
            }
        }, "all")
        
        return {
            "opportunities": [
                {
                    "symbol": opp.symbol,
                    "direction": opp.direction,
                    "entry_price": opp.entry_price,
                    "take_profit": opp.take_profit,
                    "stop_loss": opp.stop_loss,
                    "confidence": opp.confidence,
                    "leverage": opp.leverage,
                    "risk_reward": opp.risk_reward,
                    "volume_24h": opp.volume_24h,
                    "volatility": opp.volatility,
                    "score": opp.score,
                    "indicators": opp.indicators,
                    "reasoning": opp.reasoning
                }
                for opp in top_opportunities
            ],
            "total": len(filtered),
            "timestamp": datetime.now().timestamp()
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/opportunities/{symbol}")
async def get_symbol_opportunity(symbol: str):
    """Get a specific trading opportunity by symbol."""
    # Trigger a scan to ensure opportunities are up-to-date
    opportunities_list = await symbol_discovery.scan_opportunities()

    # Find the specific opportunity
    opportunity = next((opp for opp in opportunities_list if opp.symbol == symbol), None)

    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Prepare data dictionary (similar structure to get_opportunities for consistency)
    opportunity_data = clean_float_values({
        'symbol': opportunity.symbol,
        'timestamp': opportunity.timestamp.isoformat(),
        'indicators': opportunity.indicators, # Assuming indicators are JSON serializable
        'signal': opportunity.signal, # Assuming signal is JSON serializable
        'risk_reward_ratio': opportunity.risk_reward_ratio,
        'volatility_score': opportunity.volatility_score,
        'technical_score': opportunity.technical_score,
        'fundamental_score': opportunity.fundamental_score,
        'overall_score': opportunity.overall_score,
        'signal_strength': opportunity.signal_strength,
        'signal_type': opportunity.signal_type,
        'entry_price': opportunity.entry_price,
        'take_profit': opportunity.take_profit,
        'stop_loss': opportunity.stop_loss
    })

    # Clean potential NaN/Infinity values before returning
    cleaned_opportunity = clean_float_values(opportunity_data)

    return JSONResponse(content=cleaned_opportunity)

@app.get("/api/trading/opportunities/stats")
async def get_opportunity_stats():
    """Get statistics on trading opportunities."""
    db: Session = SessionLocal()
    try:
        total_trades = db.query(Trade).count()
        winning_trades = db.query(Trade).filter(Trade.pnl > 0).count()
        total_pnl_result = db.query(db.func.sum(Trade.pnl)).scalar()

        total_pnl = total_pnl_result if total_pnl_result is not None else 0

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Calculate Profit Factor: Total Gross Profit / Total Gross Loss
        # Need to query sum of winning PnL and sum of losing PnL separately
        total_gross_profit_result = db.query(db.func.sum(Trade.pnl)).filter(Trade.pnl > 0).scalar()
        total_gross_loss_result = db.query(db.func.sum(Trade.pnl)).filter(Trade.pnl < 0).scalar()

        total_gross_profit = total_gross_profit_result if total_gross_profit_result is not None else 0
        total_gross_loss = total_gross_loss_result if total_gross_loss_result is not None else 0

        # Avoid division by zero for profit factor
        profit_factor = abs(total_gross_profit / total_gross_loss) if total_gross_loss < 0 else float('inf') if total_gross_profit > 0 else 0

        # Calculate Maximum Drawdown (Simplified - requires more trade history analysis for accuracy)
        # This is a placeholder; a proper drawdown calculation needs state over time
        max_drawdown = 0 # Placeholder

        # Calculate Average Trade PnL
        average_trade_pnl = (total_pnl / total_trades) if total_trades > 0 else 0

        stats = {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown, # Placeholder
            "average_trade_pnl": average_trade_pnl,
            # Add other relevant stats here
        }

        # Clean potential NaN/Infinity values before returning
        cleaned_stats = clean_float_values(stats)

        return JSONResponse(content=cleaned_stats)

    except Exception as e:
        logger.error(f"Error fetching opportunity stats: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 