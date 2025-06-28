import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import uuid

logger = logging.getLogger(__name__)

@dataclass
class ScalpingSignalEvent:
    """Represents a scalping signal event for WebSocket broadcasting."""
    event_type: str  # 'signal_new', 'signal_update', 'signal_invalidate', 'signal_stale'
    signal_id: str
    signal_data: Dict[str, Any]
    timestamp: float
    reason: Optional[str] = None

class RealtimeScalpingManager:
    """Manages real-time scalping signals with WebSocket broadcasting and lifecycle management."""
    
    def __init__(self, opportunity_manager, exchange_client, connection_manager):
        self.opportunity_manager = opportunity_manager
        self.exchange_client = exchange_client
        self.connection_manager = connection_manager
        
        # Signal storage and tracking
        self.active_signals: Dict[str, Dict[str, Any]] = {}
        self.signal_age_limit = 15 * 60  # 15 minutes in seconds
        self.stale_warning_time = 10 * 60  # 10 minutes in seconds
        
        # Background tasks
        self.running = False
        self.signal_generation_task = None
        self.validation_task = None
        self.cleanup_task = None
        
        # Signal generation settings
        self.generation_interval = 30  # Generate new signals every 30 seconds
        self.validation_interval = 15  # Validate signals every 15 seconds
        self.cleanup_interval = 60    # Cleanup stale signals every 60 seconds
        
        logger.info("✅ Real-time Scalping Manager initialized")

    async def start(self):
        """Start the real-time scalping signal system."""
        if self.running:
            logger.warning("Real-time scalping manager already running")
            return
            
        self.running = True
        logger.info("🚀 Starting real-time scalping signal system...")
        
        # Start background tasks
        self.signal_generation_task = asyncio.create_task(self._signal_generation_loop())
        self.validation_task = asyncio.create_task(self._signal_validation_loop())
        self.cleanup_task = asyncio.create_task(self._signal_cleanup_loop())
        
        logger.info("✅ Real-time scalping system started")

    async def stop(self):
        """Stop the real-time scalping signal system."""
        self.running = False
        
        # Cancel background tasks
        if self.signal_generation_task:
            self.signal_generation_task.cancel()
        if self.validation_task:
            self.validation_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
            
        logger.info("🛑 Real-time scalping system stopped")

    async def _signal_generation_loop(self):
        """Background loop for generating new scalping signals."""
        logger.info("🔄 Starting signal generation loop")
        
        while self.running:
            try:
                await self._generate_fresh_signals()
                await asyncio.sleep(self.generation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in signal generation loop: {e}")
                await asyncio.sleep(5)

    async def _signal_validation_loop(self):
        """Background loop for validating existing signals against market conditions."""
        logger.info("🔍 Starting signal validation loop")
        
        while self.running:
            try:
                await self._validate_active_signals()
                await asyncio.sleep(self.validation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in signal validation loop: {e}")
                await asyncio.sleep(5)

    async def _signal_cleanup_loop(self):
        """Background loop for cleaning up stale and expired signals."""
        logger.info("🧹 Starting signal cleanup loop")
        
        while self.running:
            try:
                await self._cleanup_expired_signals()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in signal cleanup loop: {e}")
                await asyncio.sleep(5)

    async def _generate_fresh_signals(self):
        """Generate fresh scalping signals and broadcast new ones."""
        try:
            logger.debug("🔍 Scanning for fresh scalping opportunities...")
            
            # Get opportunities from the opportunity manager
            opportunities = self.opportunity_manager.get_opportunities()
            
            if not opportunities:
                logger.debug("No opportunities available from opportunity manager")
                return
            
            # Filter for scalping criteria (high confidence >= 70%, optimized post-slippage R/R >= 0.5)
            fresh_signals = {}
            for opp in opportunities:
                confidence = opp.get('confidence', 0)
                # Use adjusted R/R ratio if available (post-slippage), otherwise fall back to original
                risk_reward = opp.get('adjusted_rr_ratio', opp.get('risk_reward', 0))
                tradable = opp.get('tradable', True)  # Only include tradable signals
                
                # Enhanced scalping filter: confidence >= 0.7, reasonable post-slippage R/R >= 0.5, and tradable
                # Lower R/R threshold since validation now accounts for scalping-specific requirements
                if confidence >= 0.7 and risk_reward >= 0.5 and tradable:
                    # Generate stable signal ID based on CORE trading parameters only
                    # This prevents duplicate signals for the same opportunity
                    symbol = opp.get('symbol', 'UNKNOWN')
                    direction = opp.get('direction', 'UNKNOWN')
                    entry_price = opp.get('adjusted_entry', opp.get('entry_price', 0))
                    
                    # FIXED: Create stable ID based on symbol and direction only
                    # Don't include strategy or entry price as they can vary slightly
                    # This ensures one signal per symbol per direction
                    signal_id = f"{symbol}_{direction}"
                    
                    # Transform to scalping signal format with adjusted values
                    scalping_signal = {
                        'symbol': opp.get('symbol', 'Unknown'),
                        'direction': opp.get('direction', 'UNKNOWN'),
                        'strategy': opp.get('strategy', 'Unknown'),
                        'confidence': confidence,
                        'risk_reward': risk_reward,
                        # Use adjusted entry/exit prices if available for more accurate scalping
                        'entry_price': opp.get('adjusted_entry', opp.get('entry_price', 0)),
                        'stop_loss': opp.get('stop_loss', 0),
                        'take_profit': opp.get('adjusted_take_profit', opp.get('take_profit', 0)),
                        'expected_capital_return_pct': opp.get('expected_capital_return_pct', min(confidence * 10, 8.5)),
                        'optimal_leverage': opp.get('optimal_leverage', min(confidence * 4, 3.0)),
                        'scalping_type': 'momentum_scalp' if confidence >= 0.85 else 'mean_reversion_scalp',
                        'timestamp': opp.get('timestamp', datetime.now().isoformat()),
                        # Include validation data for transparency
                        'tradable': tradable,
                        'original_rr_ratio': opp.get('risk_reward', 0),
                        'adjusted_rr_ratio': risk_reward,
                        'expected_slippage_pct': opp.get('expected_slippage_pct', 0),
                        'volume_score': opp.get('volume_score', 'Unknown'),
                        'verdict': opp.get('verdict', 'Tradable')
                    }
                    
                    fresh_signals[signal_id] = scalping_signal
            
            logger.info(f"🔍 Filtered {len(fresh_signals)} scalping signals from {len(opportunities)} opportunities")
            
            # Process new signals
            new_signals_count = 0
            for signal_id, signal_data in fresh_signals.items():
                if signal_id not in self.active_signals:
                    # New signal detected
                    await self._add_new_signal(signal_id, signal_data)
                    new_signals_count += 1
                else:
                    # Existing signal - check for updates
                    await self._update_existing_signal(signal_id, signal_data)
            
            if new_signals_count > 0:
                logger.info(f"📈 Generated {new_signals_count} new scalping signals")
                
        except Exception as e:
            logger.error(f"❌ Error generating fresh signals: {e}")

    async def _add_new_signal(self, signal_id: str, signal_data: Dict[str, Any]):
        """Add a new signal and broadcast it."""
        try:
            # Add metadata
            current_time = time.time()
            signal_data.update({
                'signal_id': signal_id,
                'created_at': current_time,
                'last_updated': current_time,
                'status': 'active',
                'age_seconds': 0
            })
            
            # Store signal
            self.active_signals[signal_id] = signal_data
            
            # Create and broadcast event
            event = ScalpingSignalEvent(
                event_type='signal_new',
                signal_id=signal_id,
                signal_data=signal_data,
                timestamp=current_time
            )
            
            await self._broadcast_signal_event(event)
            
            logger.debug(f"✨ New signal added: {signal_data.get('symbol')} {signal_data.get('direction')} - {signal_data.get('expected_capital_return_pct', 0):.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error adding new signal {signal_id}: {e}")

    async def _update_existing_signal(self, signal_id: str, signal_data: Dict[str, Any]):
        """Update an existing signal if conditions changed."""
        try:
            if signal_id not in self.active_signals:
                return
                
            existing_signal = self.active_signals[signal_id]
            
            # Check if key parameters changed
            key_params = ['entry_price', 'take_profit', 'stop_loss', 'expected_capital_return_pct', 'optimal_leverage']
            has_changes = False
            
            for param in key_params:
                old_value = existing_signal.get(param, 0)
                new_value = signal_data.get(param, 0)
                if abs(old_value - new_value) > 0.0001:  # Small threshold for floating point comparison
                    has_changes = True
                    break
            
            if has_changes:
                # Update signal data
                signal_data.update({
                    'signal_id': signal_id,
                    'created_at': existing_signal.get('created_at', time.time()),
                    'last_updated': time.time(),
                    'status': existing_signal.get('status', 'active'),
                    'age_seconds': time.time() - existing_signal.get('created_at', time.time())
                })
                
                self.active_signals[signal_id] = signal_data
                
                # Broadcast update
                event = ScalpingSignalEvent(
                    event_type='signal_update',
                    signal_id=signal_id,
                    signal_data=signal_data,
                    timestamp=time.time(),
                    reason='market_conditions_changed'
                )
                
                await self._broadcast_signal_event(event)
                
                logger.debug(f"🔄 Signal updated: {signal_data.get('symbol')} - conditions changed")
                
        except Exception as e:
            logger.error(f"❌ Error updating signal {signal_id}: {e}")

    async def _validate_active_signals(self):
        """Validate active signals against current market conditions."""
        try:
            if not self.active_signals:
                return
                
            current_time = time.time()
            signals_to_remove = []
            
            for signal_id, signal_data in list(self.active_signals.items()):
                try:
                    symbol = signal_data.get('symbol')
                    entry_price = signal_data.get('entry_price', 0)
                    stop_loss = signal_data.get('stop_loss', 0)
                    take_profit = signal_data.get('take_profit', 0)
                    direction = signal_data.get('direction', '')
                    created_at = signal_data.get('created_at', current_time)
                    
                    # Calculate signal age
                    age_seconds = current_time - created_at
                    signal_data['age_seconds'] = age_seconds
                    
                    # Check if signal hit stale warning time
                    if age_seconds > self.stale_warning_time and signal_data.get('status') != 'stale':
                        signal_data['status'] = 'stale'
                        
                        event = ScalpingSignalEvent(
                            event_type='signal_stale',
                            signal_id=signal_id,
                            signal_data=signal_data,
                            timestamp=current_time,
                            reason=f'signal_age_{int(age_seconds/60)}_minutes'
                        )
                        
                        await self._broadcast_signal_event(event)
                        logger.debug(f"⚠️ Signal marked as stale: {symbol} (age: {int(age_seconds/60)} minutes)")
                    
                    # Get current market price for validation
                    try:
                        ticker = await self.exchange_client.get_ticker_24h(symbol)
                        current_price = float(ticker.get('lastPrice', 0))
                        
                        # Check if TP or SL was hit
                        signal_invalidated = False
                        invalidation_reason = ""
                        
                        if direction.upper() == 'LONG':
                            if current_price >= take_profit:
                                signal_invalidated = True
                                invalidation_reason = "take_profit_hit"
                            elif current_price <= stop_loss:
                                signal_invalidated = True
                                invalidation_reason = "stop_loss_hit"
                        elif direction.upper() == 'SHORT':
                            if current_price <= take_profit:
                                signal_invalidated = True
                                invalidation_reason = "take_profit_hit"
                            elif current_price >= stop_loss:
                                signal_invalidated = True
                                invalidation_reason = "stop_loss_hit"
                        
                        if signal_invalidated:
                            signals_to_remove.append((signal_id, invalidation_reason))
                            
                    except Exception as e:
                        logger.warning(f"Failed to get current price for {symbol}: {e}")
                        
                except Exception as e:
                    logger.error(f"Error validating signal {signal_id}: {e}")
            
            # Remove invalidated signals
            for signal_id, reason in signals_to_remove:
                await self._invalidate_signal(signal_id, reason)
                
        except Exception as e:
            logger.error(f"❌ Error validating active signals: {e}")

    async def _cleanup_expired_signals(self):
        """Remove signals that are too old (>15 minutes)."""
        try:
            if not self.active_signals:
                return
                
            current_time = time.time()
            expired_signals = []
            
            for signal_id, signal_data in self.active_signals.items():
                created_at = signal_data.get('created_at', current_time)
                age_seconds = current_time - created_at
                
                if age_seconds > self.signal_age_limit:
                    expired_signals.append(signal_id)
            
            # Remove expired signals
            for signal_id in expired_signals:
                await self._invalidate_signal(signal_id, 'expired_age_limit')
                
            if expired_signals:
                logger.info(f"🗑️ Removed {len(expired_signals)} expired signals (>15 minutes old)")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired signals: {e}")

    async def _invalidate_signal(self, signal_id: str, reason: str):
        """Invalidate and remove a signal."""
        try:
            if signal_id not in self.active_signals:
                return
                
            signal_data = self.active_signals[signal_id]
            signal_data['status'] = 'invalidated'
            signal_data['invalidation_reason'] = reason
            
            # Broadcast invalidation
            event = ScalpingSignalEvent(
                event_type='signal_invalidate',
                signal_id=signal_id,
                signal_data=signal_data,
                timestamp=time.time(),
                reason=reason
            )
            
            await self._broadcast_signal_event(event)
            
            # Remove from active signals
            del self.active_signals[signal_id]
            
            logger.debug(f"❌ Signal invalidated: {signal_data.get('symbol')} - {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error invalidating signal {signal_id}: {e}")

    async def _broadcast_signal_event(self, event: ScalpingSignalEvent):
        """Broadcast a signal event to all WebSocket connections."""
        try:
            message = {
                'type': 'scalping_signal_event',
                'event_type': event.event_type,
                'signal_id': event.signal_id,
                'signal_data': event.signal_data,
                'timestamp': event.timestamp,
                'reason': event.reason
            }
            
            await self.connection_manager.broadcast(message)
            
            logger.debug(f"📡 Broadcasted {event.event_type} for {event.signal_data.get('symbol')}")
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting signal event: {e}")

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Get all currently active signals."""
        return list(self.active_signals.values())

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary statistics of active signals."""
        if not self.active_signals:
            return {
                'total_signals': 0,
                'avg_expected_return': 0,
                'high_priority_count': 0,
                'stale_signals_count': 0,
                'avg_age_minutes': 0
            }
        
        signals = list(self.active_signals.values())
        current_time = time.time()
        
        total_signals = len(signals)
        avg_expected_return = sum(s.get('expected_capital_return_pct', 0) for s in signals) / total_signals
        high_priority_count = sum(1 for s in signals if s.get('expected_capital_return_pct', 0) >= 7)
        stale_signals_count = sum(1 for s in signals if s.get('status') == 'stale')
        avg_age_minutes = sum((current_time - s.get('created_at', current_time)) / 60 for s in signals) / total_signals
        
        return {
            'total_signals': total_signals,
            'avg_expected_return': round(avg_expected_return, 1),
            'high_priority_count': high_priority_count,
            'stale_signals_count': stale_signals_count,
            'avg_age_minutes': round(avg_age_minutes, 1)
        }

    async def force_signal_refresh(self):
        """Force an immediate signal refresh."""
        logger.info("🔄 Forcing immediate signal refresh...")
        await self._generate_fresh_signals()
        await self._validate_active_signals()
        await self._cleanup_expired_signals()

    def cleanup(self):
        """Cleanup method for graceful shutdown."""
        logger.info("🧹 Cleaning up RealtimeScalpingManager...")
        try:
            # Stop the manager if running
            if self.running:
                asyncio.create_task(self.stop())
            logger.info("✅ RealtimeScalpingManager cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error during RealtimeScalpingManager cleanup: {e}")
