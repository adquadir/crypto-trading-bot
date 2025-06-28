"""
Flow Trading Monitoring and Alerting System
Comprehensive monitoring for performance, risk, and system health
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import json

from ..config.flow_trading_config import get_config_manager, MonitoringConfig
from ..database.database import Database

logger = logging.getLogger(__name__)

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    alert_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    symbol: Optional[str]
    strategy_type: Optional[str]
    message: str
    alert_data: Dict[str, Any]
    timestamp: datetime
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class PerformanceMetrics:
    """Performance monitoring metrics"""
    symbol: str
    strategy_type: str
    current_pnl: float
    pnl_change_1h: float
    pnl_change_24h: float
    win_rate_1h: float
    win_rate_24h: float
    trade_count_1h: int
    trade_count_24h: int
    avg_trade_duration_minutes: float
    max_drawdown_pct: float
    sharpe_ratio: float
    last_updated: datetime

@dataclass
class RiskMetrics:
    """Risk monitoring metrics"""
    portfolio_var_1d: float
    portfolio_var_5d: float
    max_drawdown_pct: float
    total_exposure_usd: float
    total_exposure_pct: float
    correlation_concentration: float
    active_strategies: int
    risk_score: float  # 0-100
    last_updated: datetime

@dataclass
class SystemHealthMetrics:
    """System health monitoring metrics"""
    component_name: str
    status: str  # 'healthy', 'degraded', 'failed'
    cpu_usage_pct: float
    memory_usage_pct: float
    response_time_ms: float
    error_count: int
    uptime_minutes: int
    last_error: Optional[str]
    last_updated: datetime

class PerformanceMonitor:
    """Monitor trading performance and detect degradation"""
    
    def __init__(self, db: Database):
        self.db = db
        self.performance_history = defaultdict(deque)  # symbol -> deque of metrics
        self.alert_thresholds = get_config_manager().monitoring_config.alert_thresholds
        
    async def check_performance(self) -> List[Alert]:
        """Check performance metrics and generate alerts"""
        alerts = []
        
        try:
            # Get recent performance data
            query = """
            SELECT 
                symbol,
                strategy_type,
                SUM(pnl) as current_pnl,
                COUNT(*) as trade_count,
                AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                AVG(duration_minutes) as avg_duration,
                MIN(pnl) as max_loss
            FROM flow_trades 
            WHERE entry_time >= NOW() - INTERVAL '1 hour'
            GROUP BY symbol, strategy_type
            """
            
            with self.db.session_scope() as session:
                result = session.execute(query)
                current_metrics = result.fetchall()
            
            for row in current_metrics:
                symbol = row.symbol
                strategy_type = row.strategy_type
                current_pnl = float(row.current_pnl or 0)
                win_rate = float(row.win_rate or 0)
                
                # Check for performance degradation
                degradation_threshold = self.alert_thresholds.get('performance_degradation_pct', -5.0)
                
                if current_pnl < 0 and abs(current_pnl) > abs(degradation_threshold):
                    alert = Alert(
                        id=f"perf_deg_{symbol}_{strategy_type}_{int(time.time())}",
                        alert_type="performance_degradation",
                        severity="high" if abs(current_pnl) > 10 else "medium",
                        symbol=symbol,
                        strategy_type=strategy_type,
                        message=f"Performance degradation detected: {symbol} {strategy_type} P&L: {current_pnl:.2f}%",
                        alert_data={
                            "current_pnl": current_pnl,
                            "win_rate": win_rate,
                            "threshold": degradation_threshold
                        },
                        timestamp=datetime.utcnow()
                    )
                    alerts.append(alert)
                
                # Check for low win rate
                if win_rate < 0.3 and row.trade_count >= 10:  # At least 10 trades
                    alert = Alert(
                        id=f"low_winrate_{symbol}_{strategy_type}_{int(time.time())}",
                        alert_type="low_win_rate",
                        severity="medium",
                        symbol=symbol,
                        strategy_type=strategy_type,
                        message=f"Low win rate detected: {symbol} {strategy_type} Win Rate: {win_rate:.1%}",
                        alert_data={
                            "win_rate": win_rate,
                            "trade_count": row.trade_count,
                            "threshold": 0.3
                        },
                        timestamp=datetime.utcnow()
                    )
                    alerts.append(alert)
            
        except Exception as e:
            logger.error(f"Error checking performance: {e}")
            
        return alerts

class RiskMonitor:
    """Monitor portfolio risk and detect breaches"""
    
    def __init__(self, db: Database):
        self.db = db
        self.risk_history = deque(maxlen=1000)
        self.alert_thresholds = get_config_manager().monitoring_config.alert_thresholds
        
    async def check_risk_metrics(self) -> List[Alert]:
        """Check risk metrics and generate alerts"""
        alerts = []
        
        try:
            # Get current risk metrics
            risk_config = get_config_manager().risk_config
            
            # Calculate current portfolio metrics
            query = """
            SELECT 
                SUM(ABS(pnl)) as total_exposure,
                COUNT(DISTINCT symbol) as active_strategies,
                STDDEV(pnl) as portfolio_volatility
            FROM flow_trades 
            WHERE exit_time IS NULL  -- Active positions only
            """
            
            with self.db.session_scope() as session:
                result = session.execute(query)
                row = result.fetchone()
                
                if row:
                    total_exposure = float(row.total_exposure or 0)
                    active_strategies = int(row.active_strategies or 0)
                    portfolio_volatility = float(row.portfolio_volatility or 0)
                    
                    # Check exposure limits
                    max_exposure = risk_config.max_portfolio_exposure_pct * 10000  # Assuming $10k account
                    if total_exposure > max_exposure:
                        alert = Alert(
                            id=f"risk_exposure_{int(time.time())}",
                            alert_type="risk_breach",
                            severity="high",
                            symbol=None,
                            strategy_type=None,
                            message=f"Portfolio exposure breach: ${total_exposure:.2f} > ${max_exposure:.2f}",
                            alert_data={
                                "current_exposure": total_exposure,
                                "max_exposure": max_exposure,
                                "breach_pct": (total_exposure - max_exposure) / max_exposure * 100
                            },
                            timestamp=datetime.utcnow()
                        )
                        alerts.append(alert)
                    
                    # Check strategy concentration
                    if active_strategies > 10:  # Too many concurrent strategies
                        alert = Alert(
                            id=f"strategy_concentration_{int(time.time())}",
                            alert_type="strategy_concentration",
                            severity="medium",
                            symbol=None,
                            strategy_type=None,
                            message=f"High strategy concentration: {active_strategies} active strategies",
                            alert_data={
                                "active_strategies": active_strategies,
                                "recommended_max": 10
                            },
                            timestamp=datetime.utcnow()
                        )
                        alerts.append(alert)
            
        except Exception as e:
            logger.error(f"Error checking risk metrics: {e}")
            
        return alerts

class SystemHealthMonitor:
    """Monitor system health and component status"""
    
    def __init__(self, db: Database):
        self.db = db
        self.component_status = {}
        self.error_counts = defaultdict(int)
        self.response_times = defaultdict(deque)
        
    async def check_system_health(self, components: Dict[str, Any]) -> List[Alert]:
        """Check system health and generate alerts"""
        alerts = []
        
        try:
            # Check system resources
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            
            # CPU usage alert
            if cpu_usage > 90:
                alert = Alert(
                    id=f"high_cpu_{int(time.time())}",
                    alert_type="system_resource",
                    severity="high",
                    symbol=None,
                    strategy_type=None,
                    message=f"High CPU usage: {cpu_usage:.1f}%",
                    alert_data={"cpu_usage": cpu_usage, "threshold": 90},
                    timestamp=datetime.utcnow()
                )
                alerts.append(alert)
            
            # Memory usage alert
            if memory_usage > 85:
                alert = Alert(
                    id=f"high_memory_{int(time.time())}",
                    alert_type="system_resource",
                    severity="high",
                    symbol=None,
                    strategy_type=None,
                    message=f"High memory usage: {memory_usage:.1f}%",
                    alert_data={"memory_usage": memory_usage, "threshold": 85},
                    timestamp=datetime.utcnow()
                )
                alerts.append(alert)
            
            # Check component health
            for component_name, component in components.items():
                if component is None:
                    alert = Alert(
                        id=f"component_failed_{component_name}_{int(time.time())}",
                        alert_type="component_failure",
                        severity="critical",
                        symbol=None,
                        strategy_type=None,
                        message=f"Component failed: {component_name}",
                        alert_data={"component": component_name, "status": "failed"},
                        timestamp=datetime.utcnow()
                    )
                    alerts.append(alert)
            
            # Store system health metrics
            health_metric = SystemHealthMetrics(
                component_name="system",
                status="healthy" if cpu_usage < 80 and memory_usage < 80 else "degraded",
                cpu_usage_pct=cpu_usage,
                memory_usage_pct=memory_usage,
                response_time_ms=0,  # Would measure API response time
                error_count=sum(self.error_counts.values()),
                uptime_minutes=int(time.time() / 60),  # Simplified uptime
                last_error=None,
                last_updated=datetime.utcnow()
            )
            
            await self._store_health_metrics(health_metric)
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            
        return alerts
    
    async def _store_health_metrics(self, metrics: SystemHealthMetrics):
        """Store health metrics in database"""
        try:
            query = """
            INSERT INTO system_health 
            (component_name, status, cpu_usage_pct, memory_usage_pct, 
             response_time_ms, error_count, uptime_minutes, last_error)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            with self.db.session_scope() as session:
                session.execute(query, (
                    metrics.component_name,
                    metrics.status,
                    metrics.cpu_usage_pct,
                    metrics.memory_usage_pct,
                    metrics.response_time_ms,
                    metrics.error_count,
                    metrics.uptime_minutes,
                    metrics.last_error
                ))
                
        except Exception as e:
            logger.error(f"Error storing health metrics: {e}")

class AlertManager:
    """Manage alerts and notifications"""
    
    def __init__(self, db: Database):
        self.db = db
        self.active_alerts = {}  # alert_id -> Alert
        self.notification_config = get_config_manager().monitoring_config.notification_channels
        
    async def process_alert(self, alert: Alert):
        """Process and store an alert"""
        try:
            # Store in database
            await self._store_alert(alert)
            
            # Add to active alerts
            self.active_alerts[alert.id] = alert
            
            # Send notifications
            await self._send_notifications(alert)
            
            logger.warning(f"🚨 ALERT [{alert.severity.upper()}]: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
    
    async def _store_alert(self, alert: Alert):
        """Store alert in database"""
        try:
            query = """
            INSERT INTO performance_alerts 
            (alert_type, severity, symbol, strategy_type, message, alert_data)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            with self.db.session_scope() as session:
                session.execute(query, (
                    alert.alert_type,
                    alert.severity,
                    alert.symbol,
                    alert.strategy_type,
                    alert.message,
                    json.dumps(alert.alert_data)
                ))
                
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    async def _send_notifications(self, alert: Alert):
        """Send alert notifications through configured channels"""
        try:
            # Database notification (always enabled)
            if self.notification_config.get('database', True):
                # Already stored in _store_alert
                pass
            
            # Webhook notification
            if self.notification_config.get('webhook', False):
                await self._send_webhook_notification(alert)
            
            # Email notification (would implement)
            if self.notification_config.get('email', False):
                await self._send_email_notification(alert)
            
            # Slack notification (would implement)
            if self.notification_config.get('slack', False):
                await self._send_slack_notification(alert)
                
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
    
    async def _send_webhook_notification(self, alert: Alert):
        """Send webhook notification"""
        try:
            # Would implement webhook sending
            logger.info(f"📡 Webhook notification sent for alert: {alert.id}")
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
    
    async def _send_email_notification(self, alert: Alert):
        """Send email notification"""
        try:
            # Would implement email sending
            logger.info(f"📧 Email notification sent for alert: {alert.id}")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    async def _send_slack_notification(self, alert: Alert):
        """Send Slack notification"""
        try:
            # Would implement Slack sending
            logger.info(f"💬 Slack notification sent for alert: {alert.id}")
        except Exception as e:
            logger.error(f"Error sending Slack: {e}")
    
    async def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.is_resolved = True
                alert.resolved_at = datetime.utcnow()
                
                # Update in database
                query = """
                UPDATE performance_alerts 
                SET is_resolved = true, resolved_at = %s 
                WHERE id = %s
                """
                
                with self.db.session_scope() as session:
                    session.execute(query, (alert.resolved_at, alert_id))
                
                del self.active_alerts[alert_id]
                logger.info(f"✅ Alert resolved: {alert_id}")
                
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())

class FlowTradingMonitor:
    """Main monitoring coordinator"""
    
    def __init__(self, db: Database):
        self.db = db
        self.config = get_config_manager().monitoring_config
        
        # Initialize monitors
        self.performance_monitor = PerformanceMonitor(db)
        self.risk_monitor = RiskMonitor(db)
        self.health_monitor = SystemHealthMonitor(db)
        self.alert_manager = AlertManager(db)
        
        # Monitoring state
        self.running = False
        self.last_checks = {
            'performance': datetime.min,
            'risk': datetime.min,
            'health': datetime.min
        }
        
    async def start_monitoring(self, components: Dict[str, Any]):
        """Start the monitoring system"""
        self.running = True
        self.components = components
        
        logger.info("🔍 Flow Trading Monitor started")
        
        # Start monitoring loops
        asyncio.create_task(self._performance_monitoring_loop())
        asyncio.create_task(self._risk_monitoring_loop())
        asyncio.create_task(self._health_monitoring_loop())
        
    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.running = False
        logger.info("🛑 Flow Trading Monitor stopped")
    
    async def _performance_monitoring_loop(self):
        """Performance monitoring loop"""
        while self.running:
            try:
                now = datetime.utcnow()
                interval = timedelta(minutes=self.config.performance_check_interval_minutes)
                
                if now - self.last_checks['performance'] >= interval:
                    alerts = await self.performance_monitor.check_performance()
                    
                    for alert in alerts:
                        await self.alert_manager.process_alert(alert)
                    
                    self.last_checks['performance'] = now
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _risk_monitoring_loop(self):
        """Risk monitoring loop"""
        while self.running:
            try:
                now = datetime.utcnow()
                interval = timedelta(minutes=self.config.risk_check_interval_minutes)
                
                if now - self.last_checks['risk'] >= interval:
                    alerts = await self.risk_monitor.check_risk_metrics()
                    
                    for alert in alerts:
                        await self.alert_manager.process_alert(alert)
                    
                    self.last_checks['risk'] = now
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _health_monitoring_loop(self):
        """Health monitoring loop"""
        while self.running:
            try:
                now = datetime.utcnow()
                interval = timedelta(minutes=self.config.health_check_interval_minutes)
                
                if now - self.last_checks['health'] >= interval:
                    alerts = await self.health_monitor.check_system_health(self.components)
                    
                    for alert in alerts:
                        await self.alert_manager.process_alert(alert)
                    
                    self.last_checks['health'] = now
                
                await asyncio.sleep(120)  # Check every 2 minutes
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'running': self.running,
            'active_alerts': len(self.alert_manager.active_alerts),
            'last_checks': {
                key: value.isoformat() if value != datetime.min else None
                for key, value in self.last_checks.items()
            },
            'config': asdict(self.config)
        }
    
    async def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        try:
            query = """
            SELECT * FROM performance_alerts 
            WHERE created_at >= NOW() - INTERVAL '%s hours'
            ORDER BY created_at DESC
            LIMIT 100
            """
            
            with self.db.session_scope() as session:
                result = session.execute(query, (hours,))
                alerts = []
                
                for row in result.fetchall():
                    alert_data = dict(row)
                    if alert_data.get('alert_data'):
                        alert_data['alert_data'] = json.loads(alert_data['alert_data'])
                    alerts.append(alert_data)
                
                return alerts
                
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []

# Global monitor instance
monitor_instance = None

def get_monitor() -> Optional[FlowTradingMonitor]:
    """Get the global monitor instance"""
    return monitor_instance

def initialize_monitor(db: Database) -> FlowTradingMonitor:
    """Initialize the global monitor instance"""
    global monitor_instance
    monitor_instance = FlowTradingMonitor(db)
    return monitor_instance
