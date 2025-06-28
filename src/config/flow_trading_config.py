"""
Centralized Flow Trading Configuration Management
Handles all configurable parameters for flow trading strategies
"""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ScalpingConfig:
    """Scalping strategy configuration"""
    profit_target_pct: float = 0.005  # 0.5% profit target
    stop_loss_pct: float = 0.003      # 0.3% stop loss
    trailing_stop_pct: float = 0.002  # 0.2% trailing stop
    min_confidence: float = 0.75      # Minimum signal confidence
    max_position_time_minutes: int = 30  # Max time to hold position
    atr_multiplier: float = 2.0       # ATR multiplier for dynamic targets
    volume_threshold: float = 1.5     # Volume surge threshold
    
@dataclass
class GridTradingConfig:
    """Grid trading strategy configuration"""
    default_levels: int = 5
    default_spacing_pct: float = 0.004  # 0.4% between levels
    profit_per_level_pct: float = 0.003  # 0.3% profit per fill
    max_grid_exposure_pct: float = 0.02  # 2% of account per grid
    volatility_adjustment: bool = True
    min_volatility_threshold: float = 0.01
    max_volatility_threshold: float = 0.08
    rebalance_threshold_pct: float = 0.05  # 5% price move triggers rebalance

@dataclass
class RiskManagementConfig:
    """Risk management configuration"""
    max_portfolio_exposure_pct: float = 0.10  # 10% max portfolio exposure
    max_single_position_pct: float = 0.02     # 2% max single position
    max_correlation_concentration: float = 0.7  # Max correlation between positions
    max_portfolio_var_1d: float = 0.05       # 5% max 1-day VaR
    max_portfolio_var_5d: float = 0.12       # 12% max 5-day VaR
    max_drawdown_threshold: float = 0.15     # 15% max drawdown before stop
    stress_test_scenarios: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.stress_test_scenarios is None:
            self.stress_test_scenarios = {
                "flash_crash": {"market_drop_pct": -10.0, "volatility_spike": 3.0},
                "market_correction": {"market_drop_pct": -20.0, "volatility_spike": 2.0},
                "crypto_winter": {"market_drop_pct": -50.0, "volatility_spike": 4.0}
            }

@dataclass
class MLConfig:
    """Machine Learning configuration"""
    signal_confidence_threshold: float = 0.6
    model_retrain_interval_hours: int = 24
    feature_importance_threshold: float = 0.05
    prediction_horizon_minutes: int = 60
    ensemble_models: bool = True
    online_learning: bool = True
    model_validation_split: float = 0.2
    max_training_samples: int = 10000

@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    performance_check_interval_minutes: int = 5
    risk_check_interval_minutes: int = 1
    health_check_interval_minutes: int = 2
    alert_thresholds: Dict[str, float] = None
    notification_channels: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                "performance_degradation_pct": -5.0,  # -5% performance drop
                "risk_breach_multiplier": 1.5,        # 1.5x risk limit breach
                "system_error_count": 10,             # 10 errors in interval
                "latency_threshold_ms": 1000          # 1 second latency
            }
        
        if self.notification_channels is None:
            self.notification_channels = {
                "email": False,
                "slack": False,
                "webhook": True,
                "database": True
            }

@dataclass
class SymbolConfig:
    """Per-symbol configuration"""
    symbol: str
    enabled: bool = True
    strategy_preference: str = "adaptive"  # 'scalping', 'grid', 'adaptive'
    custom_scalping_config: Optional[ScalpingConfig] = None
    custom_grid_config: Optional[GridTradingConfig] = None
    custom_risk_config: Optional[RiskManagementConfig] = None
    min_volume_24h: float = 1000000.0  # Minimum 24h volume
    max_spread_pct: float = 0.001      # Maximum spread percentage

class FlowTradingConfigManager:
    """Centralized configuration manager for flow trading"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config/flow_trading_config.json"
        self.config_path = Path(self.config_file)
        
        # Default configurations
        self.scalping_config = ScalpingConfig()
        self.grid_config = GridTradingConfig()
        self.risk_config = RiskManagementConfig()
        self.ml_config = MLConfig()
        self.monitoring_config = MonitoringConfig()
        
        # Symbol-specific configurations
        self.symbol_configs: Dict[str, SymbolConfig] = {}
        
        # Load configuration from file
        self.load_config()
        
    def load_config(self):
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Load main configurations
                if 'scalping' in config_data:
                    self.scalping_config = ScalpingConfig(**config_data['scalping'])
                
                if 'grid_trading' in config_data:
                    self.grid_config = GridTradingConfig(**config_data['grid_trading'])
                
                if 'risk_management' in config_data:
                    self.risk_config = RiskManagementConfig(**config_data['risk_management'])
                
                if 'ml' in config_data:
                    self.ml_config = MLConfig(**config_data['ml'])
                
                if 'monitoring' in config_data:
                    self.monitoring_config = MonitoringConfig(**config_data['monitoring'])
                
                # Load symbol-specific configurations
                if 'symbols' in config_data:
                    for symbol_data in config_data['symbols']:
                        symbol_config = SymbolConfig(**symbol_data)
                        self.symbol_configs[symbol_config.symbol] = symbol_config
                
                logger.info(f"✅ Configuration loaded from {self.config_file}")
            else:
                logger.info(f"⚠️ Config file not found, using defaults: {self.config_file}")
                self.save_config()  # Save default configuration
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config_data = {
                'scalping': asdict(self.scalping_config),
                'grid_trading': asdict(self.grid_config),
                'risk_management': asdict(self.risk_config),
                'ml': asdict(self.ml_config),
                'monitoring': asdict(self.monitoring_config),
                'symbols': [asdict(config) for config in self.symbol_configs.values()],
                'last_updated': datetime.utcnow().isoformat()
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            logger.info(f"✅ Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def get_scalping_config(self, symbol: str = None) -> ScalpingConfig:
        """Get scalping configuration for symbol"""
        if symbol and symbol in self.symbol_configs:
            symbol_config = self.symbol_configs[symbol]
            if symbol_config.custom_scalping_config:
                return symbol_config.custom_scalping_config
        return self.scalping_config
    
    def get_grid_config(self, symbol: str = None) -> GridTradingConfig:
        """Get grid trading configuration for symbol"""
        if symbol and symbol in self.symbol_configs:
            symbol_config = self.symbol_configs[symbol]
            if symbol_config.custom_grid_config:
                return symbol_config.custom_grid_config
        return self.grid_config
    
    def get_risk_config(self, symbol: str = None) -> RiskManagementConfig:
        """Get risk management configuration for symbol"""
        if symbol and symbol in self.symbol_configs:
            symbol_config = self.symbol_configs[symbol]
            if symbol_config.custom_risk_config:
                return symbol_config.custom_risk_config
        return self.risk_config
    
    def get_symbol_config(self, symbol: str) -> SymbolConfig:
        """Get symbol-specific configuration"""
        if symbol not in self.symbol_configs:
            # Create default symbol configuration
            self.symbol_configs[symbol] = SymbolConfig(symbol=symbol)
        return self.symbol_configs[symbol]
    
    def update_scalping_config(self, **kwargs):
        """Update scalping configuration"""
        for key, value in kwargs.items():
            if hasattr(self.scalping_config, key):
                setattr(self.scalping_config, key, value)
        self.save_config()
    
    def update_grid_config(self, **kwargs):
        """Update grid trading configuration"""
        for key, value in kwargs.items():
            if hasattr(self.grid_config, key):
                setattr(self.grid_config, key, value)
        self.save_config()
    
    def update_risk_config(self, **kwargs):
        """Update risk management configuration"""
        for key, value in kwargs.items():
            if hasattr(self.risk_config, key):
                setattr(self.risk_config, key, value)
        self.save_config()
    
    def update_ml_config(self, **kwargs):
        """Update ML configuration"""
        for key, value in kwargs.items():
            if hasattr(self.ml_config, key):
                setattr(self.ml_config, key, value)
        self.save_config()
    
    def update_monitoring_config(self, **kwargs):
        """Update monitoring configuration"""
        for key, value in kwargs.items():
            if hasattr(self.monitoring_config, key):
                setattr(self.monitoring_config, key, value)
        self.save_config()
    
    def add_symbol(self, symbol: str, **kwargs):
        """Add or update symbol configuration"""
        if symbol in self.symbol_configs:
            # Update existing
            for key, value in kwargs.items():
                if hasattr(self.symbol_configs[symbol], key):
                    setattr(self.symbol_configs[symbol], key, value)
        else:
            # Create new
            self.symbol_configs[symbol] = SymbolConfig(symbol=symbol, **kwargs)
        self.save_config()
    
    def remove_symbol(self, symbol: str):
        """Remove symbol configuration"""
        if symbol in self.symbol_configs:
            del self.symbol_configs[symbol]
            self.save_config()
    
    def get_enabled_symbols(self) -> list:
        """Get list of enabled symbols"""
        return [symbol for symbol, config in self.symbol_configs.items() if config.enabled]
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configurations as dictionary"""
        return {
            'scalping': asdict(self.scalping_config),
            'grid_trading': asdict(self.grid_config),
            'risk_management': asdict(self.risk_config),
            'ml': asdict(self.ml_config),
            'monitoring': asdict(self.monitoring_config),
            'symbols': {symbol: asdict(config) for symbol, config in self.symbol_configs.items()}
        }
    
    def validate_config(self) -> Dict[str, list]:
        """Validate configuration and return any issues"""
        issues = {
            'errors': [],
            'warnings': []
        }
        
        # Validate scalping config
        if self.scalping_config.profit_target_pct <= 0:
            issues['errors'].append("Scalping profit target must be positive")
        
        if self.scalping_config.stop_loss_pct <= 0:
            issues['errors'].append("Scalping stop loss must be positive")
        
        if self.scalping_config.profit_target_pct <= self.scalping_config.stop_loss_pct:
            issues['warnings'].append("Scalping profit target should be larger than stop loss")
        
        # Validate grid config
        if self.grid_config.default_levels < 2:
            issues['errors'].append("Grid must have at least 2 levels")
        
        if self.grid_config.default_spacing_pct <= 0:
            issues['errors'].append("Grid spacing must be positive")
        
        # Validate risk config
        if self.risk_config.max_portfolio_exposure_pct > 1.0:
            issues['warnings'].append("Portfolio exposure > 100% is very risky")
        
        if self.risk_config.max_single_position_pct > self.risk_config.max_portfolio_exposure_pct:
            issues['errors'].append("Single position size cannot exceed portfolio exposure")
        
        # Validate ML config
        if not (0 < self.ml_config.signal_confidence_threshold < 1):
            issues['errors'].append("ML confidence threshold must be between 0 and 1")
        
        return issues

# Global configuration manager instance
config_manager = FlowTradingConfigManager()

def get_config_manager() -> FlowTradingConfigManager:
    """Get the global configuration manager instance"""
    return config_manager

def reload_config():
    """Reload configuration from file"""
    global config_manager
    config_manager.load_config()
    logger.info("Configuration reloaded")
