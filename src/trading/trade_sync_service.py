"""
Trade Synchronization Service
Monitors Binance trades and learns from manual interventions
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from ..market_data.exchange_client import ExchangeClient
from ..database.database import Database
from ..ml.ml_learning_service import MLLearningService
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class ExternalTrade:
    """Represents a trade detected from external sources (manual closure)"""
    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    source: str  # 'BINANCE_MANUAL', 'SYSTEM', 'UNKNOWN'
    pnl: Optional[float] = None
    matched_position_id: Optional[str] = None
    learning_outcome: Optional[str] = None

class TradeSyncService:
    """Service to synchronize trades and learn from manual interventions"""
    
    def __init__(self, exchange_client: Optional[ExchangeClient] = None, 
                 ml_service: Optional[MLLearningService] = None):
        self.exchange_client = exchange_client or ExchangeClient()
        self.db_manager = Database()
        self.ml_service = ml_service or MLLearningService()
        
        # Sync state
        self.is_running = False
        self.last_sync_time = datetime.now() - timedelta(hours=1)
        self.sync_interval = 30  # seconds
        
        # Trade tracking
        self.system_trades: Dict[str, Dict] = {}  # position_id -> trade_data
        self.external_trades: List[ExternalTrade] = []
        self.processed_trade_ids: Set[str] = set()
        
        # Learning statistics
        self.manual_trades_detected = 0
        self.successful_matches = 0
        self.learning_outcomes_recorded = 0
        
        logger.info("🔄 Trade Sync Service initialized")
    
    async def start_sync(self) -> bool:
        """Start the trade synchronization service"""
        try:
            if self.is_running:
                logger.warning("Trade sync service is already running")
                return False
            
            # Verify exchange connection
            if not self.exchange_client or not hasattr(self.exchange_client, 'ccxt_client'):
                logger.error("❌ No exchange connection available for trade sync")
                return False
            
            self.is_running = True
            
            # Start background sync task
            asyncio.create_task(self._sync_loop())
            
            logger.info("🔄 Trade synchronization service started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting trade sync service: {e}")
            return False
    
    async def stop_sync(self) -> bool:
        """Stop the trade synchronization service"""
        try:
            self.is_running = False
            logger.info("🔄 Trade synchronization service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping trade sync service: {e}")
            return False
    
    async def register_system_trade(self, position_id: str, trade_data: Dict[str, Any]):
        """Register a trade opened by the system"""
        try:
            self.system_trades[position_id] = {
                'position_id': position_id,
                'symbol': trade_data.get('symbol'),
                'side': trade_data.get('side'),
                'entry_price': trade_data.get('entry_price'),
                'position_size': trade_data.get('position_size'),
                'entry_time': trade_data.get('entry_time'),
                'strategy': trade_data.get('strategy'),
                'confidence': trade_data.get('confidence'),
                'status': 'OPEN',
                'expected_binance_trades': []  # Will be populated when we detect corresponding trades
            }
            
            logger.info(f"📝 Registered system trade: {position_id} - {trade_data.get('symbol')}")
            
        except Exception as e:
            logger.error(f"Error registering system trade: {e}")
    
    async def unregister_system_trade(self, position_id: str, close_data: Dict[str, Any]):
        """Unregister a trade closed by the system"""
        try:
            if position_id in self.system_trades:
                self.system_trades[position_id]['status'] = 'CLOSED_BY_SYSTEM'
                self.system_trades[position_id]['exit_price'] = close_data.get('exit_price')
                self.system_trades[position_id]['exit_time'] = close_data.get('exit_time')
                self.system_trades[position_id]['pnl'] = close_data.get('pnl')
                
                logger.info(f"📝 Unregistered system trade: {position_id} - closed by system")
                
                # Remove from active tracking after a delay (to catch any late Binance updates)
                asyncio.create_task(self._delayed_cleanup(position_id, 300))  # 5 minutes
            
        except Exception as e:
            logger.error(f"Error unregistering system trade: {e}")
    
    async def _sync_loop(self):
        """Main synchronization loop"""
        while self.is_running:
            try:
                await self._perform_sync()
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(self.sync_interval)
    
    async def _perform_sync(self):
        """Perform one synchronization cycle"""
        try:
            # Fetch recent trades from Binance
            recent_trades = await self._fetch_recent_binance_trades()
            
            if not recent_trades:
                return
            
            # Process each trade
            for trade in recent_trades:
                await self._process_binance_trade(trade)
            
            # Detect manual interventions
            await self._detect_manual_interventions()
            
            # Update learning from manual trades
            await self._update_ml_learning()
            
            self.last_sync_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Error performing sync: {e}")
    
    async def _fetch_recent_binance_trades(self) -> List[Dict]:
        """Fetch recent trades from Binance"""
        try:
            # Calculate time window for fetching trades
            since = self.last_sync_time - timedelta(minutes=5)  # 5-minute overlap for safety
            
            # Get trades for all symbols we're tracking
            all_trades = []
            symbols = set()
            
            # Collect symbols from system trades
            for trade_data in self.system_trades.values():
                if trade_data.get('symbol'):
                    symbols.add(trade_data['symbol'])
            
            # Fetch trades for each symbol
            for symbol in symbols:
                try:
                    trades = await self.exchange_client.get_recent_trades(symbol, since)
                    if trades:
                        all_trades.extend(trades)
                except Exception as e:
                    logger.warning(f"Could not fetch trades for {symbol}: {e}")
            
            logger.debug(f"Fetched {len(all_trades)} recent trades from Binance")
            return all_trades
            
        except Exception as e:
            logger.error(f"Error fetching recent Binance trades: {e}")
            return []
    
    async def _process_binance_trade(self, trade: Dict):
        """Process a single Binance trade"""
        try:
            trade_id = trade.get('id', str(trade.get('timestamp', '')))
            
            # Skip if already processed
            if trade_id in self.processed_trade_ids:
                return
            
            # Create external trade record
            external_trade = ExternalTrade(
                trade_id=trade_id,
                symbol=trade.get('symbol', ''),
                side=trade.get('side', ''),
                quantity=float(trade.get('amount', 0)),
                price=float(trade.get('price', 0)),
                timestamp=datetime.fromtimestamp(trade.get('timestamp', 0) / 1000),
                source='BINANCE_MANUAL'  # Assume manual until proven otherwise
            )
            
            # Try to match with system trades
            matched_position = await self._match_with_system_trade(external_trade)
            
            if matched_position:
                external_trade.matched_position_id = matched_position
                external_trade.source = 'SYSTEM'
                logger.debug(f"Matched Binance trade {trade_id} with system position {matched_position}")
            else:
                # This is likely a manual trade
                external_trade.source = 'BINANCE_MANUAL'
                self.manual_trades_detected += 1
                logger.info(f"🔍 Detected potential manual trade: {external_trade.symbol} {external_trade.side} @ ${external_trade.price:.2f}")
            
            self.external_trades.append(external_trade)
            self.processed_trade_ids.add(trade_id)
            
        except Exception as e:
            logger.error(f"Error processing Binance trade: {e}")
    
    async def _match_with_system_trade(self, external_trade: ExternalTrade) -> Optional[str]:
        """Try to match external trade with a system trade"""
        try:
            for position_id, system_trade in self.system_trades.items():
                # Check symbol match
                if system_trade.get('symbol') != external_trade.symbol:
                    continue
                
                # Check if this could be the opening trade
                if (system_trade.get('status') == 'OPEN' and 
                    self._is_opening_trade_match(system_trade, external_trade)):
                    return position_id
                
                # Check if this could be the closing trade
                if (system_trade.get('status') in ['OPEN', 'CLOSED_BY_SYSTEM'] and 
                    self._is_closing_trade_match(system_trade, external_trade)):
                    return position_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error matching external trade: {e}")
            return None
    
    def _is_opening_trade_match(self, system_trade: Dict, external_trade: ExternalTrade) -> bool:
        """Check if external trade matches system trade opening"""
        try:
            # Check side match
            if system_trade.get('side') != external_trade.side:
                return False
            
            # Check price proximity (within 0.1%)
            system_price = system_trade.get('entry_price', 0)
            if abs(external_trade.price - system_price) / system_price > 0.001:
                return False
            
            # Check quantity proximity (within 1%)
            system_quantity = system_trade.get('position_size', 0)
            if abs(external_trade.quantity - system_quantity) / system_quantity > 0.01:
                return False
            
            # Check time proximity (within 2 minutes)
            system_time = system_trade.get('entry_time')
            if isinstance(system_time, str):
                system_time = datetime.fromisoformat(system_time.replace('Z', '+00:00'))
            
            time_diff = abs((external_trade.timestamp - system_time).total_seconds())
            if time_diff > 120:  # 2 minutes
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking opening trade match: {e}")
            return False
    
    def _is_closing_trade_match(self, system_trade: Dict, external_trade: ExternalTrade) -> bool:
        """Check if external trade matches system trade closing"""
        try:
            # Check opposite side for closing
            system_side = system_trade.get('side')
            expected_close_side = 'SELL' if system_side == 'LONG' else 'BUY'
            
            if external_trade.side != expected_close_side:
                return False
            
            # Check quantity match (within 1%)
            system_quantity = system_trade.get('position_size', 0)
            if abs(external_trade.quantity - system_quantity) / system_quantity > 0.01:
                return False
            
            # For closing trades, we're more lenient on time (could be manual closure)
            return True
            
        except Exception as e:
            logger.error(f"Error checking closing trade match: {e}")
            return False
    
    async def _detect_manual_interventions(self):
        """Detect manual interventions in trading"""
        try:
            # Look for system positions that should have corresponding Binance trades but don't
            for position_id, system_trade in self.system_trades.items():
                if system_trade.get('status') != 'OPEN':
                    continue
                
                # Check if we have a corresponding opening trade
                has_opening_trade = any(
                    et.matched_position_id == position_id and et.source == 'SYSTEM'
                    for et in self.external_trades
                )
                
                if not has_opening_trade:
                    # This system position doesn't have a corresponding Binance trade
                    # This could indicate a problem or a very recent trade
                    logger.debug(f"System position {position_id} has no corresponding Binance opening trade")
                
                # Check for manual closures
                manual_close_trades = [
                    et for et in self.external_trades
                    if (et.symbol == system_trade.get('symbol') and
                        et.source == 'BINANCE_MANUAL' and
                        et.side == ('SELL' if system_trade.get('side') == 'LONG' else 'BUY'))
                ]
                
                for close_trade in manual_close_trades:
                    if self._could_be_manual_closure(system_trade, close_trade):
                        await self._record_manual_closure(position_id, system_trade, close_trade)
            
        except Exception as e:
            logger.error(f"Error detecting manual interventions: {e}")
    
    def _could_be_manual_closure(self, system_trade: Dict, external_trade: ExternalTrade) -> bool:
        """Check if external trade could be manual closure of system position"""
        try:
            # Check quantity match (within 5% for manual trades)
            system_quantity = system_trade.get('position_size', 0)
            if abs(external_trade.quantity - system_quantity) / system_quantity > 0.05:
                return False
            
            # Check if trade happened after position opening
            system_time = system_trade.get('entry_time')
            if isinstance(system_time, str):
                system_time = datetime.fromisoformat(system_time.replace('Z', '+00:00'))
            
            if external_trade.timestamp <= system_time:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking manual closure: {e}")
            return False
    
    async def _record_manual_closure(self, position_id: str, system_trade: Dict, close_trade: ExternalTrade):
        """Record a manual closure for learning"""
        try:
            # Calculate P&L
            entry_price = system_trade.get('entry_price', 0)
            exit_price = close_trade.price
            quantity = close_trade.quantity
            side = system_trade.get('side')
            
            if side == 'LONG':
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity
            
            # Apply leverage
            leverage = system_trade.get('leverage', 1)
            pnl *= leverage
            
            close_trade.pnl = pnl
            close_trade.matched_position_id = position_id
            close_trade.learning_outcome = 'MANUAL_CLOSURE'
            
            # Update system trade status
            self.system_trades[position_id]['status'] = 'CLOSED_MANUALLY'
            self.system_trades[position_id]['exit_price'] = exit_price
            self.system_trades[position_id]['exit_time'] = close_trade.timestamp
            self.system_trades[position_id]['pnl'] = pnl
            
            self.successful_matches += 1
            
            logger.info(f"📊 Recorded manual closure: {position_id} - P&L: ${pnl:.2f}")
            
            # Prepare learning data
            learning_data = {
                'position_id': position_id,
                'symbol': system_trade.get('symbol'),
                'strategy': system_trade.get('strategy'),
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'confidence': system_trade.get('confidence'),
                'manual_closure': True,
                'closure_reason': 'MANUAL_INTERVENTION',
                'duration_minutes': (close_trade.timestamp - datetime.fromisoformat(
                    system_trade.get('entry_time').replace('Z', '+00:00')
                )).total_seconds() / 60
            }
            
            # Send to ML learning service
            await self._send_to_ml_learning(learning_data)
            
        except Exception as e:
            logger.error(f"Error recording manual closure: {e}")
    
    async def _update_ml_learning(self):
        """Update ML learning with manual trade outcomes"""
        try:
            # Process unprocessed manual trades
            for external_trade in self.external_trades:
                if (external_trade.source == 'BINANCE_MANUAL' and 
                    external_trade.learning_outcome is None):
                    
                    # Try to infer learning from manual trade
                    learning_data = await self._infer_learning_from_manual_trade(external_trade)
                    
                    if learning_data:
                        await self._send_to_ml_learning(learning_data)
                        external_trade.learning_outcome = 'PROCESSED'
                        self.learning_outcomes_recorded += 1
            
        except Exception as e:
            logger.error(f"Error updating ML learning: {e}")
    
    async def _infer_learning_from_manual_trade(self, external_trade: ExternalTrade) -> Optional[Dict]:
        """Try to infer learning data from a manual trade"""
        try:
            # For now, we can only learn from manual trades if we can associate them
            # with system signals or positions. This is a complex inference problem.
            
            # Look for recent system signals for the same symbol
            # This would require integration with the signal tracking system
            
            # For now, return basic learning data
            return {
                'symbol': external_trade.symbol,
                'manual_trade': True,
                'trade_side': external_trade.side,
                'trade_price': external_trade.price,
                'trade_time': external_trade.timestamp,
                'learning_type': 'MANUAL_TRADE_OBSERVATION'
            }
            
        except Exception as e:
            logger.error(f"Error inferring learning from manual trade: {e}")
            return None
    
    async def _send_to_ml_learning(self, learning_data: Dict):
        """Send learning data to ML service"""
        try:
            if self.ml_service:
                await self.ml_service.record_trade_outcome(learning_data)
                logger.debug(f"Sent learning data to ML service: {learning_data.get('position_id', 'manual')}")
            
        except Exception as e:
            logger.error(f"Error sending to ML learning: {e}")
    
    async def _delayed_cleanup(self, position_id: str, delay_seconds: int):
        """Clean up old position data after delay"""
        await asyncio.sleep(delay_seconds)
        if position_id in self.system_trades:
            del self.system_trades[position_id]
            logger.debug(f"Cleaned up old position data: {position_id}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization service status"""
        try:
            return {
                'running': self.is_running,
                'last_sync': self.last_sync_time.isoformat(),
                'sync_interval_seconds': self.sync_interval,
                'system_trades_tracked': len(self.system_trades),
                'external_trades_detected': len(self.external_trades),
                'manual_trades_detected': self.manual_trades_detected,
                'successful_matches': self.successful_matches,
                'learning_outcomes_recorded': self.learning_outcomes_recorded,
                'processed_trade_ids': len(self.processed_trade_ids)
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {'running': False, 'error': str(e)}
    
    def get_manual_trades(self) -> List[Dict]:
        """Get detected manual trades"""
        try:
            manual_trades = [
                {
                    'trade_id': et.trade_id,
                    'symbol': et.symbol,
                    'side': et.side,
                    'quantity': et.quantity,
                    'price': et.price,
                    'timestamp': et.timestamp.isoformat(),
                    'source': et.source,
                    'pnl': et.pnl,
                    'matched_position_id': et.matched_position_id,
                    'learning_outcome': et.learning_outcome
                }
                for et in self.external_trades
                if et.source == 'BINANCE_MANUAL'
            ]
            
            return manual_trades
            
        except Exception as e:
            logger.error(f"Error getting manual trades: {e}")
            return []
