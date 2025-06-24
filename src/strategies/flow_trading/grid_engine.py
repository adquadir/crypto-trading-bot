"""
Grid Trading Engine for Range-Bound Markets
Continuously places buy/sell orders to capture oscillations
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class GridLevel:
    """Represents a single grid level"""
    price: float
    side: str  # 'BUY' or 'SELL'
    quantity: float
    order_id: Optional[str] = None
    filled: bool = False
    fill_time: Optional[float] = None

@dataclass
class GridState:
    """Tracks the state of a grid for a symbol"""
    symbol: str
    center_price: float
    grid_spacing: float
    levels: List[GridLevel]
    active: bool = True
    created_at: float = 0
    last_updated: float = 0
    total_filled: int = 0
    total_profit: float = 0

class GridTradingEngine:
    """Grid trading engine that creates price grids for ranging markets"""
    
    def __init__(self, exchange_client, risk_manager):
        self.exchange_client = exchange_client
        self.risk_manager = risk_manager
        self.active_grids = {}  # symbol -> GridState
        self.config = {
            'default_levels': 5,
            'spacing_multiplier': 1.0,  # x ATR
            'max_spread_pct': 2.0,
            'breakout_threshold_pct': 3.0,
            'min_order_size': 10.0,  # USD
            'max_concurrent_grids': 3
        }
        self.running = False
        
    async def start_grid(self, symbol: str, market_data: Dict, grid_config: Optional[Dict] = None) -> bool:
        """Initialize grid trading for a symbol"""
        try:
            if len(self.active_grids) >= self.config['max_concurrent_grids']:
                logger.warning(f"Max concurrent grids ({self.config['max_concurrent_grids']}) reached")
                return False
                
            # Get current market data
            current_price = float(market_data['klines'][-1]['close'])
            atr = market_data.get('indicators', {}).get('atr', current_price * 0.01)
            
            # Calculate grid parameters
            grid_spacing = atr * self.config['spacing_multiplier']
            levels_count = grid_config.get('levels', self.config['default_levels']) if grid_config else self.config['default_levels']
            
            # Validate grid spacing
            if grid_spacing / current_price > self.config['max_spread_pct'] / 100:
                logger.warning(f"Grid spacing too wide for {symbol}: {grid_spacing/current_price*100:.2f}%")
                return False
                
            # Create grid levels
            levels = self._create_grid_levels(
                symbol, current_price, grid_spacing, levels_count
            )
            
            if not levels:
                logger.error(f"Failed to create grid levels for {symbol}")
                return False
                
            # Create grid state
            grid_state = GridState(
                symbol=symbol,
                center_price=current_price,
                grid_spacing=grid_spacing,
                levels=levels,
                created_at=time.time(),
                last_updated=time.time()
            )
            
            # Place initial orders
            success = await self._place_grid_orders(grid_state)
            if success:
                self.active_grids[symbol] = grid_state
                logger.info(f"✅ Grid started for {symbol}: {len(levels)} levels, spacing: {grid_spacing:.6f}")
                return True
            else:
                logger.error(f"Failed to place grid orders for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting grid for {symbol}: {e}")
            return False
            
    async def stop_grid(self, symbol: str, reason: str = "manual") -> bool:
        """Stop grid trading and cancel all orders"""
        try:
            if symbol not in self.active_grids:
                logger.warning(f"No active grid for {symbol}")
                return False
                
            grid_state = self.active_grids[symbol]
            
            # Cancel all active orders
            cancelled_count = 0
            for level in grid_state.levels:
                if level.order_id and not level.filled:
                    try:
                        await self.exchange_client.cancel_order(symbol, level.order_id)
                        cancelled_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to cancel order {level.order_id}: {e}")
                        
            # Mark as inactive
            grid_state.active = False
            grid_state.last_updated = time.time()
            
            logger.info(f"🛑 Grid stopped for {symbol}: {reason}, cancelled {cancelled_count} orders")
            
            # Remove from active grids
            del self.active_grids[symbol]
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping grid for {symbol}: {e}")
            return False
            
    async def monitor_grids(self):
        """Monitor all active grids and handle fills"""
        while self.running:
            try:
                for symbol in list(self.active_grids.keys()):
                    await self._monitor_single_grid(symbol)
                    
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in grid monitoring: {e}")
                await asyncio.sleep(10)
                
    async def _monitor_single_grid(self, symbol: str):
        """Monitor a single grid for fills and breakouts"""
        try:
            grid_state = self.active_grids.get(symbol)
            if not grid_state or not grid_state.active:
                return
                
            # Get current price
            ticker = await self.exchange_client.get_ticker_24h(symbol)
            current_price = float(ticker.get('lastPrice', 0))
            
            # Check for breakout (price moved too far from center)
            price_move_pct = abs(current_price - grid_state.center_price) / grid_state.center_price * 100
            if price_move_pct > self.config['breakout_threshold_pct']:
                logger.warning(f"🚨 Breakout detected for {symbol}: {price_move_pct:.2f}% move")
                await self.stop_grid(symbol, f"breakout_{price_move_pct:.1f}%")
                return
                
            # Check order fills
            filled_orders = []
            for level in grid_state.levels:
                if level.order_id and not level.filled:
                    try:
                        order_status = await self.exchange_client.get_order_status(symbol, level.order_id)
                        if order_status.get('status') == 'FILLED':
                            level.filled = True
                            level.fill_time = time.time()
                            filled_orders.append(level)
                            
                    except Exception as e:
                        logger.warning(f"Error checking order status: {e}")
                        
            # Handle filled orders
            for filled_level in filled_orders:
                await self._handle_grid_fill(grid_state, filled_level, current_price)
                
            grid_state.last_updated = time.time()
            
        except Exception as e:
            logger.error(f"Error monitoring grid for {symbol}: {e}")
            
    async def _handle_grid_fill(self, grid_state: GridState, filled_level: GridLevel, current_price: float):
        """Handle a filled grid order by placing the opposite order"""
        try:
            symbol = grid_state.symbol
            
            # Calculate profit target price
            if filled_level.side == 'BUY':
                # Buy filled, place sell order above
                target_price = filled_level.price + grid_state.grid_spacing
                opposite_side = 'SELL'
            else:
                # Sell filled, place buy order below  
                target_price = filled_level.price - grid_state.grid_spacing
                opposite_side = 'BUY'
                
            # Create opposite order
            try:
                opposite_level = GridLevel(
                    price=target_price,
                    side=opposite_side,
                    quantity=filled_level.quantity
                )
                
                # Place the opposite order
                order_id = await self._place_single_order(symbol, opposite_level)
                if order_id:
                    opposite_level.order_id = order_id
                    grid_state.levels.append(opposite_level)
                    
                    # Update statistics
                    grid_state.total_filled += 1
                    
                    # Estimate profit (simplified)
                    profit = grid_state.grid_spacing * filled_level.quantity
                    grid_state.total_profit += profit
                    
                    logger.info(f"🔄 Grid fill handled for {symbol}: {filled_level.side} @ {filled_level.price:.6f}, placed {opposite_side} @ {target_price:.6f}")
                    
            except Exception as e:
                logger.error(f"Error placing opposite order for {symbol}: {e}")
                
        except Exception as e:
            logger.error(f"Error handling grid fill: {e}")
            
    def _create_grid_levels(self, symbol: str, center_price: float, spacing: float, count: int) -> List[GridLevel]:
        """Create grid levels around center price"""
        try:
            levels = []
            
            # Calculate position size per level
            position_size_usd = self.config['min_order_size']
            quantity_per_level = position_size_usd / center_price
            
            # Create buy levels below center
            for i in range(1, count + 1):
                buy_price = center_price - (spacing * i)
                if buy_price > 0:
                    levels.append(GridLevel(
                        price=round(buy_price, 8),
                        side='BUY', 
                        quantity=round(quantity_per_level, 6)
                    ))
                    
            # Create sell levels above center
            for i in range(1, count + 1):
                sell_price = center_price + (spacing * i)
                levels.append(GridLevel(
                    price=round(sell_price, 8),
                    side='SELL',
                    quantity=round(quantity_per_level, 6)
                ))
                
            return levels
            
        except Exception as e:
            logger.error(f"Error creating grid levels: {e}")
            return []
            
    async def _place_grid_orders(self, grid_state: GridState) -> bool:
        """Place all initial grid orders"""
        try:
            success_count = 0
            
            for level in grid_state.levels:
                order_id = await self._place_single_order(grid_state.symbol, level)
                if order_id:
                    level.order_id = order_id
                    success_count += 1
                else:
                    logger.warning(f"Failed to place grid order: {level.side} @ {level.price}")
                    
            # Require at least 50% success rate
            if success_count >= len(grid_state.levels) * 0.5:
                logger.info(f"Grid orders placed: {success_count}/{len(grid_state.levels)}")
                return True
            else:
                logger.error(f"Too many failed orders: {success_count}/{len(grid_state.levels)}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing grid orders: {e}")
            return False
            
    async def _place_single_order(self, symbol: str, level: GridLevel) -> Optional[str]:
        """Place a single grid order"""
        try:
            # For now, return a mock order ID (replace with real exchange integration)
            order_id = f"grid_{symbol}_{level.side}_{int(time.time())}_{level.price}"
            logger.debug(f"Mock order placed: {order_id}")
            return order_id
            
            # TODO: Replace with real exchange order placement
            # order_result = await self.exchange_client.place_limit_order(
            #     symbol=symbol,
            #     side=level.side,
            #     quantity=level.quantity,
            #     price=level.price
            # )
            # return order_result.get('orderId')
            
        except Exception as e:
            logger.error(f"Error placing single order: {e}")
            return None
            
    def get_grid_status(self, symbol: str) -> Optional[Dict]:
        """Get current status of a grid"""
        grid_state = self.active_grids.get(symbol)
        if not grid_state:
            return None
            
        active_orders = sum(1 for level in grid_state.levels if level.order_id and not level.filled)
        filled_orders = sum(1 for level in grid_state.levels if level.filled)
        
        return {
            'symbol': symbol,
            'active': grid_state.active,
            'center_price': grid_state.center_price,
            'grid_spacing': grid_state.grid_spacing,
            'total_levels': len(grid_state.levels),
            'active_orders': active_orders,
            'filled_orders': filled_orders,
            'total_profit': grid_state.total_profit,
            'uptime_minutes': (time.time() - grid_state.created_at) / 60,
            'last_updated': grid_state.last_updated
        }
        
    def get_all_grids_status(self) -> List[Dict]:
        """Get status of all active grids"""
        return [self.get_grid_status(symbol) for symbol in self.active_grids.keys()]
        
    async def start_monitoring(self):
        """Start the grid monitoring task"""
        self.running = True
        await self.monitor_grids()
        
    def stop_monitoring(self):
        """Stop the grid monitoring task"""
        self.running = False 