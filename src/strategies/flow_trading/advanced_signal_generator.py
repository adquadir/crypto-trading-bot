"""
Advanced ML-Driven Signal Generator for Flow Trading
Combines multi-timeframe analysis, sophisticated indicators, and reinforcement learning
"""

import numpy as np
import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import talib
except ImportError:
    logger.warning("TA-Lib not installed. Using basic calculations.")
    talib = None
try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("Scikit-learn not available. Using simplified ML features.")
    SKLEARN_AVAILABLE = False
    StandardScaler = None
    RandomForestClassifier = None

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available. Using simplified ML features.")
    TF_AVAILABLE = False
    tf = None

from collections import deque
import json

@dataclass
class MarketSignal:
    """Advanced market signal with confidence and reasoning"""
    symbol: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD', 'GRID_OPTIMAL'
    confidence: float  # 0.0 to 1.0
    strength: float    # Signal strength
    timeframe: str
    reasoning: Dict[str, Any]
    ml_score: float
    risk_adjusted_score: float
    expected_duration_minutes: int
    target_profit_pct: float
    stop_loss_pct: float
    timestamp: datetime

@dataclass
class MultiTimeframeData:
    """Multi-timeframe market data structure"""
    symbol: str
    timeframes: Dict[str, pd.DataFrame]  # '5m', '1h', '4h', '1d'
    indicators: Dict[str, Dict[str, np.ndarray]]
    volume_profile: Dict[str, float]
    order_book_strength: Dict[str, float]
    correlation_matrix: pd.DataFrame
    volatility_regime: str  # 'low', 'medium', 'high', 'extreme'

class AdvancedTechnicalIndicators:
    """Sophisticated technical indicators beyond basic TA"""
    
    @staticmethod
    def calculate_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI with fallback if TA-Lib not available"""
        if talib:
            return talib.RSI(close, timeperiod=period)
        else:
            # Basic RSI calculation
            delta = np.diff(close)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            
            avg_gain = pd.Series(gain).rolling(window=period).mean()
            avg_loss = pd.Series(loss).rolling(window=period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return np.concatenate([[np.nan], rsi.values])
    
    @staticmethod
    def calculate_adx_momentum_filter(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Dict[str, np.ndarray]:
        """Advanced ADX with momentum filtering"""
        if talib:
            adx = talib.ADX(high, low, close, timeperiod=period)
            plus_di = talib.PLUS_DI(high, low, close, timeperiod=period)
            minus_di = talib.MINUS_DI(high, low, close, timeperiod=period)
        else:
            # Simplified ADX calculation
            adx = np.full(len(close), 50.0)  # Default mid-range
            plus_di = np.full(len(close), 25.0)
            minus_di = np.full(len(close), 25.0)
        
        # Custom momentum filter
        momentum_strength = np.abs(plus_di - minus_di) * (adx / 100)
        trend_quality = np.where(adx > 25, 'strong', np.where(adx > 15, 'moderate', 'weak'))
        
        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'momentum_strength': momentum_strength,
            'trend_quality': trend_quality
        }
    
    @staticmethod
    def dynamic_bollinger_bands(close: np.ndarray, period: int = 20, volatility_factor: float = 2.0) -> Dict[str, np.ndarray]:
        """Dynamic Bollinger Bands with volatility-adjusted multiplier"""
        # Calculate volatility regime
        volatility = pd.Series(close).rolling(period).std()
        volatility_percentile = pd.Series(volatility).rolling(100).rank(pct=True)
        
        # Adjust multiplier based on volatility regime
        dynamic_multiplier = np.where(
            volatility_percentile > 0.8, volatility_factor * 1.5,  # High volatility
            np.where(volatility_percentile < 0.2, volatility_factor * 0.7, volatility_factor)  # Low volatility
        )
        
        sma = pd.Series(close).rolling(period).mean()
        std = pd.Series(close).rolling(period).std()
        
        upper_band = sma + (std * dynamic_multiplier)
        lower_band = sma - (std * dynamic_multiplier)
        
        # Band squeeze detection
        band_width = (upper_band - lower_band) / sma
        squeeze_threshold = np.percentile(band_width.dropna(), 20)
        is_squeeze = band_width < squeeze_threshold
        
        return {
            'upper_band': upper_band.values,
            'lower_band': lower_band.values,
            'middle_band': sma.values,
            'band_width': band_width.values,
            'is_squeeze': is_squeeze.values,
            'volatility_regime': volatility_percentile.values
        }
    
    @staticmethod
    def volume_surge_detector(volume: np.ndarray, close: np.ndarray, period: int = 20) -> Dict[str, np.ndarray]:
        """Detect volume surges and their significance"""
        avg_volume = pd.Series(volume).rolling(period).mean()
        volume_ratio = volume / avg_volume
        
        # Price-volume relationship
        price_change = np.diff(close, prepend=close[0])
        volume_price_correlation = pd.Series(price_change).rolling(period).corr(pd.Series(volume))
        
        # Volume surge classification
        surge_level = np.where(
            volume_ratio > 3.0, 'extreme',
            np.where(volume_ratio > 2.0, 'high', 
            np.where(volume_ratio > 1.5, 'moderate', 'normal'))
        )
        
        return {
            'volume_ratio': volume_ratio,
            'avg_volume': avg_volume.values,
            'surge_level': surge_level,
            'price_volume_correlation': volume_price_correlation.values
        }
    
    @staticmethod
    def market_structure_analyzer(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Dict[str, Any]:
        """Analyze market structure and pattern recognition"""
        # Swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(close) - 2):
            if high[i] > high[i-1] and high[i] > high[i-2] and high[i] > high[i+1] and high[i] > high[i+2]:
                swing_highs.append((i, high[i]))
            if low[i] < low[i-1] and low[i] < low[i-2] and low[i] < low[i+1] and low[i] < low[i+2]:
                swing_lows.append((i, low[i]))
        
        # Trend structure
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            higher_highs = swing_highs[-1][1] > swing_highs[-2][1]
            higher_lows = swing_lows[-1][1] > swing_lows[-2][1]
            
            if higher_highs and higher_lows:
                trend_structure = 'uptrend'
            elif not higher_highs and not higher_lows:
                trend_structure = 'downtrend'
            else:
                trend_structure = 'consolidation'
        else:
            trend_structure = 'insufficient_data'
        
        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'trend_structure': trend_structure,
            'structure_strength': len(swing_highs) + len(swing_lows)
        }

class ReinforcementLearningAgent:
    """RL Agent for trading decision optimization"""
    
    def __init__(self, state_size: int = 50, action_size: int = 4):
        self.state_size = state_size
        self.action_size = action_size  # 0: HOLD, 1: BUY, 2: SELL, 3: GRID
        self.memory = deque(maxlen=10000)
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        
        if TF_AVAILABLE:
            self.model = self._build_model()
            self.target_model = self._build_model()
            self.update_target_model()
        else:
            self.model = None
            self.target_model = None
            logger.warning("TensorFlow not available. RL agent will use simplified decision making.")
        
    def _build_model(self):
        """Build deep Q-network"""
        if not TF_AVAILABLE:
            return None
            
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(128, input_dim=self.state_size, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(self.action_size, activation='linear')
        ])
        model.compile(loss='mse', optimizer=tf.keras.optimizers.Adam(lr=self.learning_rate))
        return model
    
    def update_target_model(self):
        """Update target network"""
        if self.model and self.target_model:
            self.target_model.set_weights(self.model.get_weights())
    
    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay buffer"""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state):
        """Choose action using epsilon-greedy policy"""
        if not TF_AVAILABLE or not self.model:
            # Simplified decision making without TensorFlow
            return np.random.choice(self.action_size)
            
        if np.random.random() <= self.epsilon:
            return np.random.choice(self.action_size)
        
        q_values = self.model.predict(state.reshape(1, -1), verbose=0)
        return np.argmax(q_values[0])
    
    def replay(self, batch_size=32):
        """Train the model on a batch of experiences"""
        if len(self.memory) < batch_size:
            return
            
        batch = np.random.choice(len(self.memory), batch_size, replace=False)
        
        states = np.array([self.memory[i][0] for i in batch])
        actions = np.array([self.memory[i][1] for i in batch])
        rewards = np.array([self.memory[i][2] for i in batch])
        next_states = np.array([self.memory[i][3] for i in batch])
        dones = np.array([self.memory[i][4] for i in batch])
        
        target_q_values = self.target_model.predict(next_states, verbose=0)
        max_target_q_values = np.max(target_q_values, axis=1)
        
        target_q = rewards + (0.95 * max_target_q_values * (1 - dones))
        
        target_f = self.model.predict(states, verbose=0)
        for i, action in enumerate(actions):
            target_f[i][action] = target_q[i]
        
        self.model.fit(states, target_f, epochs=1, verbose=0)
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

class AdvancedSignalGenerator:
    """Main ML-driven signal generator"""
    
    def __init__(self, exchange_client):
        self.exchange_client = exchange_client
        self.indicators = AdvancedTechnicalIndicators()
        self.rl_agent = ReinforcementLearningAgent()
        
        # Initialize ML components if available
        if SKLEARN_AVAILABLE:
            self.scaler = StandardScaler()
            self.rf_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            self.scaler = None
            self.rf_classifier = None
            logger.warning("Scikit-learn not available. Using simplified feature processing.")
            
        self.signal_history = deque(maxlen=1000)
        self.performance_tracker = {}
        
        # Multi-timeframe configuration
        self.timeframes = ['5m', '1h', '4h', '1d']
        self.lookback_periods = {'5m': 200, '1h': 100, '4h': 50, '1d': 30}
        
    async def get_multi_timeframe_data(self, symbol: str) -> MultiTimeframeData:
        """Fetch and process multi-timeframe data"""
        timeframe_data = {}
        indicators = {}
        
        for tf in self.timeframes:
            try:
                # Mock data for now - replace with real exchange data
                periods = self.lookback_periods[tf]
                mock_data = self._generate_mock_ohlcv(symbol, tf, periods)
                
                df = pd.DataFrame(mock_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                
                timeframe_data[tf] = df
                
                # Calculate indicators for this timeframe
                indicators[tf] = self._calculate_all_indicators(df)
                
            except Exception as e:
                logger.error(f"Error processing data for {symbol} {tf}: {e}")
                continue
        
        # Calculate volume profile and order book analysis
        volume_profile = self._analyze_volume_profile(symbol, timeframe_data.get('5m'))
        order_book_strength = self._analyze_order_book(symbol)
        
        # Correlation analysis
        correlation_matrix = self._calculate_correlations(timeframe_data)
        
        # Volatility regime detection
        volatility_regime = self._detect_volatility_regime(timeframe_data.get('1h'))
        
        return MultiTimeframeData(
            symbol=symbol,
            timeframes=timeframe_data,
            indicators=indicators,
            volume_profile=volume_profile,
            order_book_strength=order_book_strength,
            correlation_matrix=correlation_matrix,
            volatility_regime=volatility_regime
        )
    
    def _generate_mock_ohlcv(self, symbol: str, timeframe: str, periods: int) -> List[List]:
        """Generate mock OHLCV data for testing"""
        import random
        import time
        
        # Base price simulation
        base_price = 50000.0
        current_time = int(time.time() * 1000)
        
        # Timeframe intervals in milliseconds
        intervals = {'5m': 5*60*1000, '1h': 60*60*1000, '4h': 4*60*60*1000, '1d': 24*60*60*1000}
        interval = intervals.get(timeframe, 5*60*1000)
        
        data = []
        price = base_price
        
        for i in range(periods):
            timestamp = current_time - (periods - i) * interval
            
            # Simulate price movement with some volatility
            change_pct = random.uniform(-0.02, 0.02)  # ±2% max change
            price_change = price * change_pct
            
            open_price = price
            high_price = price + abs(price_change) * random.uniform(0.5, 1.5)
            low_price = price - abs(price_change) * random.uniform(0.5, 1.5)
            close_price = price + price_change
            
            # Ensure high >= low
            if high_price < low_price:
                high_price, low_price = low_price, high_price
            
            # Ensure OHLC relationships
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            volume = random.uniform(1000, 10000)
            
            data.append([timestamp, open_price, high_price, low_price, close_price, volume])
            price = close_price
        
        return data
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Calculate all technical indicators for a timeframe"""
        high, low, close, volume = df['high'].values, df['low'].values, df['close'].values, df['volume'].values
        
        indicators = {}
        
        # Advanced ADX with momentum filter
        adx_data = self.indicators.calculate_adx_momentum_filter(high, low, close)
        indicators.update(adx_data)
        
        # Dynamic Bollinger Bands
        bb_data = self.indicators.dynamic_bollinger_bands(close)
        indicators.update(bb_data)
        
        # Volume surge detection
        volume_data = self.indicators.volume_surge_detector(volume, close)
        indicators.update(volume_data)
        
        # Additional indicators
        indicators['rsi'] = self.indicators.calculate_rsi(close)
        
        # Basic MACD calculation if TA-Lib not available
        if talib:
            indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(close)
            indicators['atr'] = talib.ATR(high, low, close, timeperiod=14)
        else:
            # Simplified MACD
            ema_12 = pd.Series(close).ewm(span=12).mean()
            ema_26 = pd.Series(close).ewm(span=26).mean()
            indicators['macd'] = (ema_12 - ema_26).values
            indicators['macd_signal'] = pd.Series(indicators['macd']).ewm(span=9).mean().values
            indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
            
            # Simplified ATR
            tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
            indicators['atr'] = pd.Series(tr).rolling(14).mean().values
        
        return indicators
    
    def _analyze_volume_profile(self, symbol: str, df_5m: pd.DataFrame) -> Dict[str, float]:
        """Analyze volume profile and distribution"""
        if df_5m is None or df_5m.empty:
            return {'high_volume_node': 0, 'low_volume_node': 0, 'volume_imbalance': 0}
        
        # Price-volume analysis
        price_levels = np.linspace(df_5m['low'].min(), df_5m['high'].max(), 50)
        volume_at_price = np.zeros(len(price_levels))
        
        for i, (_, row) in enumerate(df_5m.iterrows()):
            price_idx = np.argmin(np.abs(price_levels - row['close']))
            volume_at_price[price_idx] += row['volume']
        
        high_volume_node = price_levels[np.argmax(volume_at_price)]
        low_volume_node = price_levels[np.argmin(volume_at_price[volume_at_price > 0])] if np.any(volume_at_price > 0) else 0
        
        # Volume imbalance calculation
        recent_volume = df_5m['volume'].tail(20).mean()
        avg_volume = df_5m['volume'].mean()
        volume_imbalance = (recent_volume - avg_volume) / avg_volume if avg_volume > 0 else 0
        
        return {
            'high_volume_node': high_volume_node,
            'low_volume_node': low_volume_node,
            'volume_imbalance': volume_imbalance
        }
    
    def _analyze_order_book(self, symbol: str) -> Dict[str, float]:
        """Analyze order book strength and imbalances (mock implementation)"""
        # Mock order book analysis
        return {
            'bid_strength': 1000.0,
            'ask_strength': 1200.0,
            'imbalance': -0.09,  # Slightly bearish
            'support_levels': [49500, 49000, 48500],
            'resistance_levels': [50500, 51000, 51500]
        }
    
    def _calculate_correlations(self, timeframe_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Calculate cross-timeframe correlations"""
        if not timeframe_data:
            return pd.DataFrame()
        
        correlation_data = {}
        for tf, df in timeframe_data.items():
            if not df.empty:
                returns = df['close'].pct_change().dropna()
                if len(returns) > 0:
                    correlation_data[f'{tf}_returns'] = returns
        
        if correlation_data:
            # Align series by taking minimum length
            min_length = min(len(series) for series in correlation_data.values())
            aligned_data = {}
            for key, series in correlation_data.items():
                aligned_data[key] = series.iloc[-min_length:].reset_index(drop=True)
            
            return pd.DataFrame(aligned_data).corr()
        
        return pd.DataFrame()
    
    def _detect_volatility_regime(self, df_1h: pd.DataFrame) -> str:
        """Detect current volatility regime"""
        if df_1h is None or df_1h.empty:
            return 'unknown'
        
        # Calculate volatility metrics
        returns = df_1h['close'].pct_change().dropna()
        if len(returns) < 24:
            return 'unknown'
        
        volatility = returns.rolling(24).std()  # 24-hour rolling volatility
        
        if volatility.empty:
            return 'unknown'
        
        current_vol = volatility.iloc[-1]
        vol_percentile = (volatility <= current_vol).mean()
        
        if vol_percentile > 0.9:
            return 'extreme'
        elif vol_percentile > 0.7:
            return 'high'
        elif vol_percentile > 0.3:
            return 'medium'
        else:
            return 'low'
    
    def _prepare_ml_features(self, mt_data: MultiTimeframeData) -> np.ndarray:
        """Prepare feature vector for ML models"""
        features = []
        
        for tf in self.timeframes:
            if tf in mt_data.indicators:
                indicators = mt_data.indicators[tf]
                
                # Add last values of key indicators
                for key in ['rsi', 'macd', 'adx', 'momentum_strength', 'volume_ratio']:
                    if key in indicators and len(indicators[key]) > 0:
                        last_val = indicators[key][-1] if not np.isnan(indicators[key][-1]) else 0
                        features.append(last_val)
                    else:
                        features.append(0)
        
        # Add volume profile features
        features.extend([
            mt_data.volume_profile.get('volume_imbalance', 0),
            mt_data.order_book_strength.get('imbalance', 0)
        ])
        
        # Add volatility regime (encoded)
        vol_encoding = {'low': 0, 'medium': 1, 'high': 2, 'extreme': 3, 'unknown': 1}
        features.append(vol_encoding.get(mt_data.volatility_regime, 1))
        
        return np.array(features)
    
    async def generate_advanced_signal(self, symbol: str) -> MarketSignal:
        """Generate comprehensive ML-driven trading signal"""
        try:
            # Get multi-timeframe data
            mt_data = await self.get_multi_timeframe_data(symbol)
            
            if not mt_data.timeframes:
                return self._create_hold_signal(symbol, "insufficient_data")
            
            # Prepare features for ML models
            features = self._prepare_ml_features(mt_data)
            
            if len(features) == 0:
                return self._create_hold_signal(symbol, "no_features")
            
            # Pad or truncate features to expected size
            if len(features) < self.rl_agent.state_size:
                features = np.pad(features, (0, self.rl_agent.state_size - len(features)))
            elif len(features) > self.rl_agent.state_size:
                features = features[:self.rl_agent.state_size]
            
            # Get RL agent decision
            rl_action = self.rl_agent.act(features)
            action_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL', 3: 'GRID_OPTIMAL'}
            rl_signal = action_map[rl_action]
            
            # Multi-timeframe confirmation logic
            confirmation_score = self._calculate_multi_timeframe_confirmation(mt_data)
            
            # Risk-adjusted signal strength
            risk_score = self._calculate_risk_score(mt_data)
            
            # Final signal generation with ML integration
            final_signal, confidence = self._integrate_signals(
                rl_signal, confirmation_score, risk_score, mt_data
            )
            
            # Calculate signal parameters
            target_profit, stop_loss, duration = self._calculate_signal_parameters(
                final_signal, mt_data, confidence
            )
            
            # Create comprehensive reasoning
            reasoning = self._create_signal_reasoning(mt_data, confirmation_score, risk_score)
            
            signal = MarketSignal(
                symbol=symbol,
                signal_type=final_signal,
                confidence=confidence,
                strength=confirmation_score,
                timeframe='multi',
                reasoning=reasoning,
                ml_score=rl_action / 3.0,  # Normalize to 0-1
                risk_adjusted_score=risk_score,
                expected_duration_minutes=duration,
                target_profit_pct=target_profit,
                stop_loss_pct=stop_loss,
                timestamp=datetime.utcnow()
            )
            
            # Store signal for learning
            self.signal_history.append(signal)
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating advanced signal for {symbol}: {e}")
            return self._create_hold_signal(symbol, f"error: {str(e)}")
    
    def _calculate_multi_timeframe_confirmation(self, mt_data: MultiTimeframeData) -> float:
        """Calculate multi-timeframe confirmation score"""
        scores = []
        
        for tf in self.timeframes:
            if tf not in mt_data.indicators:
                continue
            
            indicators = mt_data.indicators[tf]
            tf_score = 0
            
            # RSI analysis
            if 'rsi' in indicators and len(indicators['rsi']) > 0:
                rsi = indicators['rsi'][-1]
                if not np.isnan(rsi):
                    if rsi < 30:
                        tf_score += 0.3  # Oversold
                    elif rsi > 70:
                        tf_score -= 0.3  # Overbought
                    else:
                        tf_score += 0.1  # Neutral
            
            # MACD analysis
            if 'macd_hist' in indicators and len(indicators['macd_hist']) > 1:
                macd_hist = indicators['macd_hist'][-2:]
                if not np.any(np.isnan(macd_hist)) and len(macd_hist) >= 2:
                    if macd_hist[-1] > macd_hist[-2] and macd_hist[-1] > 0:
                        tf_score += 0.2
                    elif macd_hist[-1] < macd_hist[-2] and macd_hist[-1] < 0:
                        tf_score -= 0.2
            
            # ADX trend strength
            if 'adx' in indicators and len(indicators['adx']) > 0:
                adx = indicators['adx'][-1]
                if not np.isnan(adx) and adx > 25:
                    tf_score += 0.2
            
            # Volume confirmation
            if 'volume_ratio' in indicators and len(indicators['volume_ratio']) > 0:
                vol_ratio = indicators['volume_ratio'][-1]
                if not np.isnan(vol_ratio) and vol_ratio > 1.5:
                    tf_score += 0.3
            
            scores.append(tf_score)
        
        return np.mean(scores) if scores else 0.0
    
    def _calculate_risk_score(self, mt_data: MultiTimeframeData) -> float:
        """Calculate comprehensive risk score"""
        risk_factors = []
        
        # Volatility risk
        vol_risk_map = {'low': 0.2, 'medium': 0.5, 'high': 0.8, 'extreme': 1.0, 'unknown': 0.5}
        vol_risk = vol_risk_map.get(mt_data.volatility_regime, 0.5)
        risk_factors.append(vol_risk)
        
        # Order book imbalance risk
        ob_imbalance = abs(mt_data.order_book_strength.get('imbalance', 0))
        risk_factors.append(min(ob_imbalance, 1.0))
        
        # Volume surge risk
        if '5m' in mt_data.indicators and 'volume_ratio' in mt_data.indicators['5m']:
            vol_ratio = mt_data.indicators['5m']['volume_ratio'][-1]
            if not np.isnan(vol_ratio):
                vol_surge_risk = min((vol_ratio - 1) / 3, 1.0)
                risk_factors.append(vol_surge_risk)
        
        return 1.0 - np.mean(risk_factors)  # Higher score = lower risk
    
    def _integrate_signals(self, rl_signal: str, confirmation_score: float, risk_score: float, mt_data: MultiTimeframeData) -> Tuple[str, float]:
        """Integrate all signals into final decision"""
        # Base confidence from confirmation score
        base_confidence = abs(confirmation_score)
        
        # Adjust for risk
        risk_adjusted_confidence = base_confidence * risk_score
        
        # Special handling for grid optimal conditions
        if rl_signal == 'GRID_OPTIMAL':
            # Check if market conditions are suitable for grid trading
            volatility_suitable = mt_data.volatility_regime in ['low', 'medium']
            
            if '1h' in mt_data.indicators and 'is_squeeze' in mt_data.indicators['1h']:
                squeeze_condition = mt_data.indicators['1h']['is_squeeze'][-1] if len(mt_data.indicators['1h']['is_squeeze']) > 0 else False
                if squeeze_condition and volatility_suitable:
                    return 'GRID_OPTIMAL', min(risk_adjusted_confidence + 0.2, 1.0)
        
        # For directional signals, require strong confirmation
        if confirmation_score > 0.3 and risk_adjusted_confidence > 0.6:
            return 'BUY', risk_adjusted_confidence
        elif confirmation_score < -0.3 and risk_adjusted_confidence > 0.6:
            return 'SELL', risk_adjusted_confidence
        elif rl_signal == 'GRID_OPTIMAL' and risk_adjusted_confidence > 0.4:
            return 'GRID_OPTIMAL', risk_adjusted_confidence
        else:
            return 'HOLD', max(risk_adjusted_confidence, 0.1)
    
    def _calculate_signal_parameters(self, signal_type: str, mt_data: MultiTimeframeData, confidence: float) -> Tuple[float, float, int]:
        """Calculate target profit, stop loss, and expected duration"""
        base_atr = 0
        if '1h' in mt_data.indicators and 'atr' in mt_data.indicators['1h']:
            atr_values = mt_data.indicators['1h']['atr']
            if len(atr_values) > 0 and not np.isnan(atr_values[-1]):
                base_atr = atr_values[-1]
        
        # Get current price for percentage calculations
        current_price = 50000  # Mock price
        if '5m' in mt_data.timeframes and not mt_data.timeframes['5m'].empty:
            current_price = mt_data.timeframes['5m']['close'].iloc[-1]
        
        atr_pct = (base_atr / current_price) * 100 if current_price > 0 else 1.0
        
        if signal_type == 'GRID_OPTIMAL':
            # Grid trading parameters
            target_profit = atr_pct * 0.5 * confidence
            stop_loss = atr_pct * 3.0
            duration = int(240 * (1 + confidence))  # 4-8 hours
        elif signal_type in ['BUY', 'SELL']:
            # Directional trading parameters
            target_profit = atr_pct * 2.0 * confidence
            stop_loss = atr_pct * 1.0
            duration = int(60 * (1 + confidence))  # 1-2 hours
        else:  # HOLD
            target_profit = 0
            stop_loss = atr_pct * 2.0
            duration = 30
        
        return target_profit, stop_loss, duration
    
    def _create_signal_reasoning(self, mt_data: MultiTimeframeData, confirmation_score: float, risk_score: float) -> Dict[str, Any]:
        """Create detailed reasoning for the signal"""
        reasoning = {
            'multi_timeframe_score': confirmation_score,
            'risk_score': risk_score,
            'volatility_regime': mt_data.volatility_regime,
            'order_book_imbalance': mt_data.order_book_strength.get('imbalance', 0),
            'volume_analysis': mt_data.volume_profile,
            'timeframe_analysis': {}
        }
        
        # Add timeframe-specific analysis
        for tf in self.timeframes:
            if tf in mt_data.indicators:
                indicators = mt_data.indicators[tf]
                tf_analysis = {}
                
                # Key indicator values
                for key in ['rsi', 'adx', 'macd_hist']:
                    if key in indicators and len(indicators[key]) > 0:
                        val = indicators[key][-1]
                        tf_analysis[key] = val if not np.isnan(val) else None
                
                reasoning['timeframe_analysis'][tf] = tf_analysis
        
        return reasoning
    
    def _create_hold_signal(self, symbol: str, reason: str) -> MarketSignal:
        """Create a default HOLD signal"""
        return MarketSignal(
            symbol=symbol,
            signal_type='HOLD',
            confidence=0.1,
            strength=0.0,
            timeframe='unknown',
            reasoning={'reason': reason},
            ml_score=0.0,
            risk_adjusted_score=0.0,
            expected_duration_minutes=30,
            target_profit_pct=0.0,
            stop_loss_pct=2.0,
            timestamp=datetime.utcnow()
        )
    
    async def update_model_with_performance(self, signal: MarketSignal, actual_return: float, duration_minutes: int):
        """Update ML models based on actual performance"""
        try:
            # Calculate reward for RL agent
            expected_return = signal.target_profit_pct / 100
            reward = actual_return / expected_return if expected_return != 0 else actual_return
            
            # Prepare state and next state (simplified)
            state = np.random.random(self.rl_agent.state_size)  # This would be the actual state
            next_state = np.random.random(self.rl_agent.state_size)  # This would be the next state
            
            action_map = {'HOLD': 0, 'BUY': 1, 'SELL': 2, 'GRID_OPTIMAL': 3}
            action = action_map.get(signal.signal_type, 0)
            
            done = duration_minutes >= signal.expected_duration_minutes
            
            # Store experience for RL training
            self.rl_agent.remember(state, action, reward, next_state, done)
            
            # Train RL agent
            if len(self.rl_agent.memory) > 32:
                self.rl_agent.replay(32)
            
            # Update performance tracking
            if signal.symbol not in self.performance_tracker:
                self.performance_tracker[signal.symbol] = []
            
            self.performance_tracker[signal.symbol].append({
                'signal_type': signal.signal_type,
                'confidence': signal.confidence,
                'expected_return': expected_return,
                'actual_return': actual_return,
                'duration': duration_minutes,
                'timestamp': datetime.utcnow()
            })
            
            logger.info(f"Updated models for {signal.symbol}: expected={expected_return:.4f}, actual={actual_return:.4f}")
            
        except Exception as e:
            logger.error(f"Error updating models: {e}") 