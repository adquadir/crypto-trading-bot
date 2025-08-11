import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Alert,
  Stack,
  Divider,
  Switch,
  FormControlLabel,
  useMediaQuery,
  useTheme,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  IconButton,
  Tabs,
  Tab
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  School as LearningIcon,
  Analytics as AnalyticsIcon,
  SmartToy as AIIcon,
  Timeline as TimelineIcon,
  AccountBalance as BalanceIcon,
  Speed as SpeedIcon,
  Close as CloseIcon,
  Settings as SettingsIcon,
  AutoAwesome as AdaptiveIcon,
  Rocket as BreakoutIcon,
  BarChart as SupportResistanceIcon,
  FlashOn as MomentumIcon,
  Info as InfoIcon,
  History as HistoryIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';
import axios from 'axios';
import config from '../config';
import { formatDuration } from '../utils/timeUtils';

const PaperTrading = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const [status, setStatus] = useState(null);
  const [positions, setPositions] = useState([]);
  const [completedTrades, setCompletedTrades] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [learningInsights, setLearningInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);
  const [closingPositions, setClosingPositions] = useState(new Set());
  const [startingEngine, setStartingEngine] = useState(false);
  const [stoppingEngine, setStoppingEngine] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  // 🔧 POSITION ID NORMALIZATION HELPER - Handles backend field name variations
  const getPositionId = (pos) => {
    if (!pos || typeof pos !== 'object') return undefined;
    // Most common variants first; extend as needed
    for (const key of ['id', 'position_id', 'trade_id', '_id', 'uid']) {
      if (pos[key] !== undefined && pos[key] !== null) return String(pos[key]);
    }
    // As a fallback, try a composite (symbol + entry_time) if backend supports it
    if (pos.symbol && pos.entry_time) return `${pos.symbol}::${pos.entry_time}`;
    return undefined;
  };

  // 🎯 SIGNAL SOURCE DISPLAY MAPPING - Clear, accurate names
  const getSignalSourceDisplay = (signalSource) => {
    const sourceMap = {
      // Profit Scraping Engine
      'profit_scraping_support': 'Profit Scraping (Support)',
      'profit_scraping_resistance': 'Profit Scraping (Resistance)',
      'profit_scraping_engine': 'Profit Scraping Engine',
      'profit_scraping': 'Profit Scraping',
      
      // Opportunity Manager + Profit Scraping Integration
      'opportunity_manager': 'Opportunity Manager',
      'opportunity_scalping': 'Opportunity Manager (Scalping)',
      'opportunity_swing': 'Opportunity Manager (Swing)',
      'opportunity_profit_scraping': 'Opportunity Manager (Profit Scraping)', // 🔥 FIX: This was causing "Opportunity Profit"
      
      // Flow Trading System
      'flow_trading_adaptive': 'Flow Trading (Adaptive)',
      'flow_trading_breakout': 'Flow Trading (Breakout)',
      'flow_trading_support_resistance': 'Flow Trading (S/R)',
      'flow_trading_momentum': 'Flow Trading (Momentum)',
      'flow_trading_engine': 'Flow Trading Engine',
      
      // Auto Signal Generator
      'auto_signal_generator': 'Auto Signal Generator',
      'auto_signal_scalping': 'Auto Signals (Scalping)',
      'auto_signal_swing': 'Auto Signals (Swing)',
      
      // Scalping Engine
      'scalping_engine': 'Scalping Engine',
      'realtime_scalping': 'Realtime Scalping',
      
      // Generic/Fallback
      'unknown': 'Unknown Source',
      'manual': 'Manual Trade',
      'other': 'Other Strategy'
    };
    
    return sourceMap[signalSource] || signalSource || 'Unknown Source';
  };

  // 🎨 SIGNAL SOURCE COLOR MAPPING - Visual distinction
  const getSignalSourceColor = (signalSource) => {
    if (signalSource?.startsWith('profit_scraping')) return 'primary';
    if (signalSource?.startsWith('opportunity')) return 'secondary';
    if (signalSource?.startsWith('flow_trading')) return 'info';
    if (signalSource?.startsWith('auto_signal')) return 'warning';
    if (signalSource?.startsWith('scalping')) return 'success';
    return 'default';
  };
  const [availableStrategies, setAvailableStrategies] = useState({
    adaptive: {
      name: "🤖 Adaptive Strategy",
      description: "Automatically selects best approach based on market conditions",
      best_for: "All market conditions - auto-adapts",
      risk_level: "Medium",
      features: ["Market regime detection", "Dynamic SL/TP", "Correlation filtering", "Volume triggers"]
    },
    breakout: {
      name: "🚀 Breakout Strategy", 
      description: "Trades breakouts from key levels in trending markets",
      best_for: "Strong trending markets with high momentum",
      risk_level: "High",
      features: ["Trend following", "Momentum confirmation", "Volume breakouts", "Extended targets"]
    },
    support_resistance: {
      name: "📊 Support/Resistance Strategy",
      description: "Trades bounces from support and resistance levels",
      best_for: "Ranging markets with clear levels",
      risk_level: "Medium",
      features: ["Level validation", "Bounce confirmation", "Range trading", "Quick scalps"]
    },
    momentum: {
      name: "⚡ Momentum Strategy",
      description: "Trades high-volume momentum moves",
      best_for: "High volume periods with strong momentum",
      risk_level: "High", 
      features: ["Volume spikes", "Momentum indicators", "Fast execution", "Quick exits"]
    }
  });
  const [currentStrategy, setCurrentStrategy] = useState('adaptive');
  const [changingStrategy, setChangingStrategy] = useState(false);
  
  // NEW: Pure 3-Rule Mode state
  const [ruleMode, setRuleMode] = useState({
    pure_3_rule_mode: true,
    mode_name: "Pure 3-Rule Mode",
    primary_target_dollars: 10.0,
    absolute_floor_dollars: 7.0,
    stop_loss_percent: 0.5
  });
  const [changingRuleMode, setChangingRuleMode] = useState(false);
  const [showRuleConfig, setShowRuleConfig] = useState(false);

  // Signal source toggles (independent)
  const [signalSources, setSignalSources] = useState({
    profit_scraping_enabled: true,
    opportunity_manager_enabled: true,
  });
  const [updatingSignalSource, setUpdatingSignalSource] = useState(null);

  const fetchSignalSources = async () => {
    try {
      const res = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/signal-sources`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data?.data) {
        setSignalSources({
          profit_scraping_enabled: Boolean(data.data.profit_scraping_enabled),
          opportunity_manager_enabled: Boolean(data.data.opportunity_manager_enabled),
        });
      }
    } catch (_) {
      // Graceful fallback if backend route isn't live yet
      setSignalSources((prev) => prev);
    }
  };

  const handleSignalSourceToggle = async (sourceKey, enabled) => {
    try {
      setUpdatingSignalSource(sourceKey);
      const res = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/signal-sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [sourceKey]: enabled }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data?.status === 'error') {
        throw new Error(data?.message || data?.detail || `Failed to toggle ${sourceKey}`);
      }
      setSignalSources((prev) => ({ ...prev, [sourceKey]: enabled }));
      setError(`✅ ${sourceKey.replace('_', ' ')} ${enabled ? 'enabled' : 'disabled'}`);
      setTimeout(() => setError(null), 2500);
    } catch (e) {
      setError(e.message || `Failed to toggle ${sourceKey}`);
    } finally {
      setUpdatingSignalSource(null);
    }
  };

  const fetchData = async () => {
    try {
      console.log("🔄 Fetching paper trading data...");
      console.log("📡 API Base URL:", config.API_BASE_URL);
      const [statusRes, positionsRes, completedTradesRes, performanceRes, strategiesRes, currentStrategyRes, ruleModeRes] = await Promise.all([
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/status`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/positions`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/trades`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/performance`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/strategies`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/strategy`),
        fetch(`${config.API_BASE_URL}/api/v1/paper-trading/rule-mode`)
      ]);

      console.log("🔍 Response statuses:", {
        status: statusRes.status,
        positions: positionsRes.status,
        trades: completedTradesRes.status,
        performance: performanceRes.status
      });

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        console.log("✅ Status data:", statusData);
        
        // API returns data directly, not wrapped in statusData.data
        // Fix for virtual_balance showing 0 due to initialization issue
        const virtualBalance = statusData.balance === 0.0 && statusData.initial_balance > 0
          ? statusData.initial_balance 
          : statusData.balance;
        
        setStatus({
          ...statusData,
          virtual_balance: virtualBalance
        });
        
        // Set running state from backend - use is_running field
        setIsRunning(statusData.is_running || false);
      } else {
        console.error("❌ Status request failed:", statusRes.status, statusRes.statusText);
      }

      if (positionsRes.ok) {
        const positionsData = await positionsRes.json();
        console.log("📊 Positions data:", positionsData);
        console.log("📊 Positions array length:", Array.isArray(positionsData) ? positionsData.length : 0);
        // API returns direct array of positions
        const positionsArray = Array.isArray(positionsData) ? positionsData : [];
        
        // Calculate age for each position
        const positionsWithAge = positionsArray.map(position => {
          const entryTime = new Date(position.entry_time);
          const now = new Date();
          const ageMinutes = Math.floor((now - entryTime) / (1000 * 60));
          
          return {
            ...position,
            age_minutes: ageMinutes
          };
        });
        
        setPositions(positionsWithAge);
      } else {
        console.error("❌ Positions request failed:", positionsRes.status, positionsRes.statusText);
      }

      if (completedTradesRes.ok) {
        const completedTradesData = await completedTradesRes.json();
        // API returns direct array, not wrapped in trades object
        const tradesArray = Array.isArray(completedTradesData) ? completedTradesData : [];
        setCompletedTrades(tradesArray);
      } else {
        console.error("❌ Completed trades request failed:", completedTradesRes.status, completedTradesRes.statusText);
      }

      if (performanceRes.ok) {
        const performanceData = await performanceRes.json();
        // API returns performance data directly, not wrapped in data object
        setPerformance(performanceData || {});
      } else {
        console.error("❌ Performance request failed:", performanceRes.status, performanceRes.statusText);
      }

      if (strategiesRes.ok) {
        const strategiesData = await strategiesRes.json();
        if (strategiesData.data?.available_strategies && Object.keys(strategiesData.data.available_strategies).length > 0) {
          setAvailableStrategies(strategiesData.data.available_strategies);
        }
        // If API fails, keep the default strategies already set in state
      }

      if (currentStrategyRes.ok) {
        const currentStrategyData = await currentStrategyRes.json();
        setCurrentStrategy(currentStrategyData.data?.current_strategy || 'adaptive');
      }
      // If API fails, keep the default 'adaptive' strategy

      if (ruleModeRes.ok) {
        const ruleModeData = await ruleModeRes.json();
        if (ruleModeData.data) {
          setRuleMode(ruleModeData.data);
        }
      }
      // If API fails, keep the default rule mode state

      // Fetch signal sources
      await fetchSignalSources();
    } catch (error) {
      console.error('Failed to fetch paper trading data:', error);
      console.error('Error details:', {
        message: error.message,
        stack: error.stack,
        name: error.name
      });
      setError(`Failed to fetch data: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Set up polling for real-time updates
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      setStartingEngine(true); // Show loading immediately
      setError(null); // Clear any existing errors
      
      const response = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        // Immediate visual feedback
        setIsRunning(true); // Optimistically update button state
        
        // Fetch real status to confirm
        await fetchData();
        setError(null);
        
        // Show success message briefly
        setError('✅ Paper trading started successfully!');
        setTimeout(() => setError(null), 3000);
      } else {
        setError(data.message || 'Failed to start paper trading');
      }
    } catch (error) {
      console.error('Error starting paper trading:', error);
      setError('Failed to start paper trading - Network error');
    } finally {
      setStartingEngine(false); // Hide loading
    }
  };

  const handleStop = async () => {
    try {
      setStoppingEngine(true); // Show loading immediately
      setError(null); // Clear any existing errors
      
      const response = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        // Immediate visual feedback
        setIsRunning(false); // Optimistically update button state
        
        // Fetch real status to confirm
        await fetchData();
        setError(null);
        
        // Show success message briefly
        setError('✅ Paper trading stopped successfully!');
        setTimeout(() => setError(null), 3000);
      } else {
        setError(data.message || 'Failed to stop paper trading');
      }
    } catch (error) {
      console.error('Error stopping paper trading:', error);
      setError('Failed to stop paper trading - Network error');
    } finally {
      setStoppingEngine(false); // Hide loading
    }
  };

  const handleStrategyChange = async (newStrategy) => {
    try {
      setChangingStrategy(true);
      const response = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/strategy?strategy=${newStrategy}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setCurrentStrategy(newStrategy);
        setError(null);
        // Refresh data to show updated strategy
        await fetchData();
      } else {
        setError(data.message || 'Failed to change strategy');
      }
    } catch (error) {
      console.error('Error changing strategy:', error);
      setError('Failed to change strategy - Network error');
    } finally {
      setChangingStrategy(false);
    }
  };

  // NEW: Rule mode handler functions
  const handleRuleModeToggle = async (newMode) => {
    try {
      setChangingRuleMode(true);
      const response = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/rule-mode?pure_3_rule_mode=${newMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setRuleMode(prev => ({ ...prev, pure_3_rule_mode: newMode, mode_name: data.data.new_mode }));
        setError(null);
        // Refresh data to show updated mode
        await fetchData();
        
        // Show success message
        setError(`✅ ${data.message}`);
        setTimeout(() => setError(null), 3000);
      } else {
        setError(data.message || 'Failed to change rule mode');
      }
    } catch (error) {
      console.error('Error changing rule mode:', error);
      setError('Failed to change rule mode - Network error');
    } finally {
      setChangingRuleMode(false);
    }
  };

  const handleRuleConfigUpdate = async (newConfig) => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/paper-trading/rule-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setRuleMode(prev => ({ 
          ...prev, 
          primary_target_dollars: data.data.primary_target_dollars,
          absolute_floor_dollars: data.data.absolute_floor_dollars,
          stop_loss_percent: data.data.stop_loss_percent
        }));
        setError(null);
        
        // Show success message
        setError(`✅ ${data.message}`);
        setTimeout(() => setError(null), 3000);
      } else {
        setError(data.detail || 'Failed to update rule configuration');
      }
    } catch (error) {
      console.error('Error updating rule configuration:', error);
      setError('Failed to update rule configuration - Network error');
    }
  };

  const getStrategyIcon = (strategy) => {
    switch (strategy) {
      case 'adaptive': return <AdaptiveIcon />;
      case 'breakout': return <BreakoutIcon />;
      case 'support_resistance': return <SupportResistanceIcon />;
      case 'momentum': return <MomentumIcon />;
      default: return <SettingsIcon />;
    }
  };

  const getStrategyColor = (strategy) => {
    switch (strategy) {
      case 'adaptive': return 'primary';
      case 'breakout': return 'success';
      case 'support_resistance': return 'info';
      case 'momentum': return 'warning';
      default: return 'default';
    }
  };

  const getReturnColor = (returnPct) => {
    if (returnPct > 0) return 'success.main';
    if (returnPct < 0) return 'error.main';
    return 'text.primary';
  };

  const getPnLColor = (pnl) => {
    if (pnl > 0) return 'success.main';
    if (pnl < 0) return 'error.main';
    return 'text.primary';
  };

  const handleClosePosition = async (positionOrId) => {
    const positionId = typeof positionOrId === 'string' ? positionOrId : getPositionId(positionOrId);
    try {
      console.log(`🔄 CLOSE REQUEST: Starting close for position ${positionId}`);
      
      if (!positionId) {
        console.error(`❌ CLOSE ERROR: Invalid position ID from position payload`);
        setError(`Invalid position ID from position payload`);
        return;
      }
      
      const position = positions.find(p => getPositionId(p) === positionId);
      if (!position) {
        console.error(`❌ CLOSE ERROR: Position ${positionId} not found in current positions`);
        console.log(`📊 Available positions:`, positions.map(p => ({ id: getPositionId(p), symbol: p.symbol })));
        setError(`Position ${positionId} not found`);
        return;
      }
      
      console.log(`✅ CLOSE VALIDATION: Position found - ${position.symbol} ${position.side}`);
      
      // Prevent duplicate close requests
      if (closingPositions.has(positionId)) {
        console.warn(`⚠️ CLOSE DUPLICATE: Already closing position ${positionId}`);
        return;
      }
      
      setClosingPositions(prev => new Set([...prev, positionId]));
      console.log(`🔒 CLOSE LOCK: Position ${positionId} marked as closing`);
      
      const requestBody = { exit_reason: 'manual_close' };
      const url = `${config.API_BASE_URL}/api/v1/paper-trading/positions/${encodeURIComponent(positionId)}/close`;
      console.log(`📤 CLOSE REQUEST:`, { url, method: 'POST', body: requestBody });
      
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      
      console.log(`📥 CLOSE RESPONSE: Status ${response.status} ${response.statusText}`);
      
      let data;
      try {
        data = await response.json();
        console.log(`📋 CLOSE DATA:`, data);
      } catch (parseError) {
        console.error(`❌ CLOSE PARSE ERROR: Failed to parse response`, parseError);
        setError('Invalid response from server');
        return;
      }
      
      if (response.ok) {
        if (data.status === 'success') {
          console.log(`✅ CLOSE SUCCESS: Position ${positionId} closed successfully`);
          console.log(`💰 CLOSE RESULT: P&L ${data.trade?.pnl || 'unknown'}, New Balance: ${data.account_update?.new_balance || 'unknown'}`);
          
          // Success - refresh data to show updated positions
          await fetchData();
          setError(null);
          
          // Show success message briefly
          setError(`✅ Position closed successfully: ${position.symbol} P&L $${data.trade?.pnl?.toFixed(2) || '0.00'}`);
          setTimeout(() => setError(null), 5000);
        } else {
          console.error(`❌ CLOSE FAILED: Server returned success=false`, data);
          setError(data.message || data.detail || 'Failed to close position');
        }
      } else {
        console.error(`❌ CLOSE HTTP ERROR: ${response.status}`, data);
        setError(data.detail || data.message || `HTTP ${response.status}: Failed to close position`);
      }
    } catch (error) {
      console.error(`❌ CLOSE NETWORK ERROR: ${error.message}`, error);
      setError(`Network error: ${error.message}`);
    } finally {
      setClosingPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(positionId);
        console.log(`🔓 CLOSE UNLOCK: Position ${positionId} removed from closing set`);
        return newSet;
      });
    }
  };

  if (loading && !status) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={{ xs: 1, sm: 2, md: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight="bold" display="flex" alignItems="center" gap={1}>
            <AIIcon color="primary" />
            Flow Trading Paper Trading
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real market conditions • Zero risk • Flow Trading strategies
          </Typography>
        </Box>
        <Box display="flex" gap={1} alignItems="center">
          <Chip
            label={isRunning ? "LIVE TRADING" : "STOPPED"}
            color={isRunning ? "success" : "default"}
            icon={isRunning ? <LearningIcon /> : <StopIcon />}
            sx={{ fontWeight: 'bold' }}
          />
          <Button
            variant="contained"
            color={isRunning ? "error" : "success"}
            onClick={isRunning ? handleStop : handleStart}
            startIcon={
              startingEngine || stoppingEngine ? 
                <CircularProgress size={20} color="inherit" /> :
                isRunning ? <StopIcon /> : <StartIcon />
            }
            disabled={loading || startingEngine || stoppingEngine}
            sx={{ 
              minWidth: '140px',
              fontWeight: 'bold',
              '&:disabled': {
                opacity: 0.7
              }
            }}
          >
            {startingEngine ? 'Starting...' : 
             stoppingEngine ? 'Stopping...' :
             isRunning ? "Stop Trading" : "Start Trading"}
          </Button>
        </Box>
      </Box>

      {/* Flow Trading Strategy Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
            <SettingsIcon color="primary" />
            Flow Trading Strategy Selection
          </Typography>
          
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Trading Strategy</InputLabel>
                <Select
                  value={currentStrategy}
                  label="Trading Strategy"
                  onChange={(e) => handleStrategyChange(e.target.value)}
                  disabled={changingStrategy || isRunning}
                  startAdornment={getStrategyIcon(currentStrategy)}
                >
                  {Object.entries(availableStrategies).map(([key, strategy]) => (
                    <MenuItem key={key} value={key}>
                      <Box display="flex" alignItems="center" gap={1}>
                        {getStrategyIcon(key)}
                        {strategy.name}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={8}>
              {availableStrategies[currentStrategy] && (
                <Box>
                  <Typography variant="body1" fontWeight="bold" gutterBottom>
                    {availableStrategies[currentStrategy].name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {availableStrategies[currentStrategy].description}
                  </Typography>
                  <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                    <Chip 
                      label={`Best for: ${availableStrategies[currentStrategy].best_for}`}
                      size="small" 
                      color="info" 
                      variant="outlined"
                    />
                    <Chip 
                      label={`Risk: ${availableStrategies[currentStrategy].risk_level}`}
                      size="small" 
                      color={availableStrategies[currentStrategy].risk_level === 'High' ? 'error' : 'warning'} 
                      variant="outlined"
                    />
                  </Box>
                  <Box mt={1}>
                    <Typography variant="caption" color="text.secondary">
                      Features: {availableStrategies[currentStrategy].features?.join(', ')}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Grid>
          </Grid>

          {changingStrategy && (
            <Box display="flex" alignItems="center" gap={1} mt={2}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">
                Changing strategy...
              </Typography>
            </Box>
          )}

          {isRunning && (
            <Alert severity="info" sx={{ mt: 2 }}>
              <Typography variant="body2">
                <strong>Note:</strong> Strategy changes are disabled while trading is active. 
                Stop trading first to change strategies.
              </Typography>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Pure 3-Rule Mode Configuration */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
            🎯 Pure 3-Rule Mode Configuration
          </Typography>
          
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>Pure 3-Rule Mode:</strong> Clean hierarchy with only 3 exit conditions: 
              $10 Take Profit → $7 Floor Protection → 0.5% Stop Loss. 
              Complex Mode includes all technical exits.
            </Typography>
          </Alert>

          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={6}>
              <Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={ruleMode.pure_3_rule_mode}
                      onChange={(e) => handleRuleModeToggle(e.target.checked)}
                      disabled={changingRuleMode}
                      color="primary"
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight="bold">
                        {ruleMode.mode_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {ruleMode.pure_3_rule_mode 
                          ? "Clean hierarchy: $10 TP → $7 Floor → 0.5% SL"
                          : "All exit conditions active"
                        }
                      </Typography>
                    </Box>
                  }
                />
                
                {changingRuleMode && (
                  <Box display="flex" alignItems="center" gap={1} mt={1}>
                    <CircularProgress size={16} />
                    <Typography variant="body2" color="text.secondary">
                      Changing mode...
                    </Typography>
                  </Box>
                )}
              </Box>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="body2" fontWeight="bold" gutterBottom>
                  Current Rule Configuration:
                </Typography>
                <Box display="flex" gap={2} flexWrap="wrap">
                  <Chip 
                    label={`Target: $${ruleMode.primary_target_dollars}`}
                    color="success" 
                    size="small"
                    variant="outlined"
                  />
                  <Chip 
                    label={`Floor: $${ruleMode.absolute_floor_dollars}`}
                    color="warning" 
                    size="small"
                    variant="outlined"
                  />
                  <Chip 
                    label={`Stop Loss: ${ruleMode.stop_loss_percent}%`}
                    color="error" 
                    size="small"
                    variant="outlined"
                  />
                </Box>
                
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => setShowRuleConfig(!showRuleConfig)}
                  sx={{ mt: 1 }}
                  startIcon={<SettingsIcon />}
                >
                  {showRuleConfig ? 'Hide Config' : 'Configure Rules'}
                </Button>
              </Box>
            </Grid>
          </Grid>

          {/* Rule Configuration Panel */}
          {showRuleConfig && (
            <Box mt={3} p={2} bgcolor="background.default" borderRadius={1}>
              <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                ⚙️ Rule Configuration (applies to new positions)
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Primary Target (dollars)
                    </Typography>
                    <Typography variant="h6" color="success.main" fontWeight="bold">
                      ${ruleMode.primary_target_dollars}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Immediate exit when reached
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Absolute Floor (dollars)
                    </Typography>
                    <Typography variant="h6" color="warning.main" fontWeight="bold">
                      ${ruleMode.absolute_floor_dollars}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Cannot drop below once reached
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Stop Loss (percent)
                    </Typography>
                    <Typography variant="h6" color="error.main" fontWeight="bold">
                      {ruleMode.stop_loss_percent}%
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Maximum loss protection
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
              
              <Alert severity="warning" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>Note:</strong> Rule configuration changes only apply to new positions. 
                  Existing positions will continue using their original rules.
                </Typography>
              </Alert>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Signal Source Toggles */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            🎯 Signal Sources
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={!!signalSources.profit_scraping_enabled}
                    onChange={(e) => handleSignalSourceToggle('profit_scraping_enabled', e.target.checked)}
                    disabled={!!updatingSignalSource}
                    color="primary"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body1" fontWeight="bold">Profit Scraper</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Allow Profit Scraper to open **new** positions.
                    </Typography>
                  </Box>
                }
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={!!signalSources.opportunity_manager_enabled}
                    onChange={(e) => handleSignalSourceToggle('opportunity_manager_enabled', e.target.checked)}
                    disabled={!!updatingSignalSource}
                    color="secondary"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body1" fontWeight="bold">Opportunity Manager</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Allow Opportunity Manager to open **new** positions.
                    </Typography>
                  </Box>
                }
              />
            </Grid>
          </Grid>

          {updatingSignalSource && (
            <Box display="flex" alignItems="center" gap={1} mt={1}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">
                Updating {updatingSignalSource.replace('_',' ')}…
              </Typography>
            </Box>
          )}

          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              These toggles only affect <strong>new</strong> entries. Existing positions continue under their original rules.
            </Typography>
          </Alert>
        </CardContent>
      </Card>

      {error && (
        <Alert 
          severity={error.includes('✅') ? 'success' : 'error'} 
          sx={{ mb: 3 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      {/* Status Overview */}
      {status && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={2.4}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <BalanceIcon color="primary" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="primary">
                  ${status.virtual_balance?.toLocaleString() || '0'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Virtual Balance
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <TrendingUpIcon sx={{ mb: 1, color: getReturnColor(status.total_return_pct) }} />
                <Typography 
                  variant="h5" 
                  fontWeight="bold"
                  color={getReturnColor(status.total_return_pct)}
                >
                  {status.total_return_pct?.toFixed(1) || '0'}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Total Return
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <SpeedIcon color="success" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="success.main">
                  {status.win_rate_pct?.toFixed(1) || '0'}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Win Rate
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <AnalyticsIcon color="info" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="info.main">
                  {status.completed_trades || 0}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ML Training Trades
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <TimelineIcon color="warning" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="warning.main">
                  {status.active_positions || 0}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Active Positions
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Flow Trading Configuration */}
      {status && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
              {getStrategyIcon(currentStrategy)}
              Flow Trading Configuration (Virtual Testing)
            </Typography>
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="body2">
                <strong>Virtual Money Testing:</strong> This uses the Flow Trading strategy with 4-layer approach: 
                Market Regime Detection, Dynamic SL/TP, Correlation Filtering, and Volume/Momentum Triggers. 
                Uses $10,000 virtual money with $1,000 per position - no real trades executed.
              </Typography>
            </Alert>
            <Grid container spacing={3}>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h6" color="primary" fontWeight="bold">
                    ${status.capital_per_position || 1000}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Virtual Capital Per Position
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h6" color="success.main" fontWeight="bold">
                    {status.leverage || 10}x
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Virtual Leverage
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h6" color="info.main" fontWeight="bold">
                    Flow Trading
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    4-Layer Approach
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h6" color={getStrategyColor(currentStrategy)} fontWeight="bold">
                    {availableStrategies[currentStrategy]?.name?.replace('🤖 ', '').replace('🚀 ', '').replace('📊 ', '').replace('⚡ ', '') || 'Strategy'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Current Strategy
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Learning Insights Alert */}
      {status?.learning_insights && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            🧠 Real-Time ML Learning Insights
          </Typography>
          {status.learning_insights.map((insight, index) => (
            <Typography key={index} variant="body2" sx={{ mb: 0.5 }}>
              • {insight}
            </Typography>
          ))}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Strategy Performance */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                🎯 Flow Trading Strategy Performance
              </Typography>
              {status?.strategy_performance && Object.entries(status.strategy_performance).map(([strategy, data]) => (
                <Box key={strategy} sx={{ mb: 2 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" fontWeight="bold" textTransform="capitalize">
                      {strategy.replace('_', ' ')}
                    </Typography>
                    <Chip 
                      label={`${(data.win_rate * 100).toFixed(1)}%`}
                      color={data.win_rate > 0.6 ? 'success' : data.win_rate > 0.5 ? 'warning' : 'error'}
                      size="small"
                    />
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={data.win_rate * 100}
                    color={data.win_rate > 0.6 ? 'success' : data.win_rate > 0.5 ? 'warning' : 'error'}
                    sx={{ height: 8, borderRadius: 1, mb: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {data.total_trades} trades • Avg PnL: ${data.avg_pnl?.toFixed(2)}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Grid>

        {/* Positions and Trades Tabs */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                <Tabs 
                  value={activeTab} 
                  onChange={(e, newValue) => setActiveTab(newValue)}
                  variant="fullWidth"
                >
                  <Tab 
                    icon={<TimelineIcon />} 
                    label="Active Positions" 
                    iconPosition="start"
                  />
                  <Tab 
                    icon={<HistoryIcon />} 
                    label="Completed Trades" 
                    iconPosition="start"
                  />
                </Tabs>
              </Box>

              {/* Active Positions Tab */}
              {activeTab === 0 && (
                <Box>
                  <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
                    <TimelineIcon color="primary" />
                    Live Virtual Positions ({positions?.length || 0})
                  </Typography>
                  {console.log("🎯 RENDER CHECK - Positions length:", positions?.length, "Positions:", positions)}
                  {console.log("🎯 RENDER CHECK - Positions type:", typeof positions, "Is Array:", Array.isArray(positions))}
                  {console.log("🎯 RENDER CHECK - Raw positions data:", JSON.stringify(positions, null, 2))}
                  
                  {/* FORCE DISPLAY TEST - Show table if we have any positions data */}
                  {(Array.isArray(positions) && positions.length > 0) || positions ? (
                    <TableContainer component={Paper} sx={{ maxHeight: 400, overflowX: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Symbol</TableCell>
                            <TableCell>Side</TableCell>
                            <TableCell>Signal Source</TableCell>
                            <TableCell align="right">Entry Price</TableCell>
                            <TableCell align="right">Current Price</TableCell>
                            <TableCell align="right">Price Change</TableCell>
                            <TableCell align="right">PnL</TableCell>
                            <TableCell align="right">Age</TableCell>
                            <TableCell align="center">Action</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {positions.map((position, index) => {
                            const pid = getPositionId(position);
                            const priceChange = position.current_price && position.entry_price 
                              ? ((position.current_price - position.entry_price) / position.entry_price) * 100
                              : 0;
                            const priceChangeColor = priceChange > 0 ? 'success.main' : priceChange < 0 ? 'error.main' : 'text.secondary';
                            
                            return (
                              <TableRow key={pid || index}>
                                <TableCell>
                                  <Typography variant="body2" fontWeight="bold">
                                    {position.symbol}
                                  </Typography>
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={position.side}
                                    color={position.side === 'LONG' ? 'success' : 'error'}
                                    size="small"
                                  />
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={getSignalSourceDisplay(position.strategy)}
                                    color={getSignalSourceColor(position.strategy)}
                                    size="small"
                                    variant="outlined"
                                    title={`${getSignalSourceDisplay(position.strategy)} - ${position.entry_reason || 'No details available'}`}
                                  />
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="body2" fontWeight="bold">
                                    ${position.entry_price?.toFixed(4) || '0.0000'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography 
                                    variant="body2" 
                                    fontWeight="bold"
                                    color={priceChangeColor}
                                  >
                                    ${position.current_price?.toFixed(4) || '0.0000'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography
                                    variant="body2"
                                    color={priceChangeColor}
                                    fontWeight="bold"
                                  >
                                    {priceChange > 0 ? '+' : ''}{priceChange.toFixed(2)}%
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography
                                    variant="body2"
                                    color={getPnLColor(position.unrealized_pnl)}
                                    fontWeight="bold"
                                  >
                                    ${position.unrealized_pnl?.toFixed(2)}
                                    <br />
                                    <Typography variant="caption" component="span">
                                      ({position.unrealized_pnl_pct?.toFixed(1)}%)
                                    </Typography>
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="caption">
                                    {formatDuration(position.age_minutes)}
                                  </Typography>
                                </TableCell>
                                <TableCell align="center">
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    color="error"
                                    startIcon={closingPositions.has(pid) ? <CircularProgress size={16} /> : <CloseIcon />}
                                    onClick={() => handleClosePosition(position)}
                                    disabled={!pid || closingPositions.has(pid)}
                                    sx={{ minWidth: 'auto', px: 1 }}
                                  >
                                    {closingPositions.has(pid) ? 'Closing...' : 'Close'}
                                  </Button>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                      No active positions
                    </Typography>
                  )}
                </Box>
              )}

              {/* Completed Trades Tab */}
              {activeTab === 1 && (
                <Box>
                  <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
                    <HistoryIcon color="primary" />
                    Completed Trades ({completedTrades?.length || 0})
                  </Typography>
                  {completedTrades?.length > 0 ? (
                    <TableContainer component={Paper} sx={{ maxHeight: 400, overflowX: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Symbol</TableCell>
                            <TableCell>Side</TableCell>
                            <TableCell>Signal Source</TableCell>
                            <TableCell align="right">Entry Price</TableCell>
                            <TableCell align="right">Exit Price</TableCell>
                            <TableCell align="right">PnL</TableCell>
                            <TableCell align="right">Fees</TableCell>
                            <TableCell align="right">Duration</TableCell>
                            <TableCell align="center">Result</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {completedTrades.map((trade, index) => {
                            const isWin = trade.pnl_usdt > 0;  // Use pnl_usdt instead of pnl
                            const pnlColor = isWin ? 'success.main' : 'error.main';
                            
                            // Calculate duration from entry and exit times
                            let durationMinutes = null;
                            if (trade.entry_time && trade.exit_time) {
                              const entryTime = new Date(trade.entry_time);
                              const exitTime = new Date(trade.exit_time);
                              durationMinutes = Math.floor((exitTime - entryTime) / (1000 * 60));
                            }
                            
                            return (
                              <TableRow key={index}>
                                <TableCell>
                                  <Typography variant="body2" fontWeight="bold">
                                    {trade.symbol}
                                  </Typography>
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={trade.side}
                                    color={trade.side === 'LONG' ? 'success' : 'error'}
                                    size="small"
                                  />
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={getSignalSourceDisplay(trade.strategy)}  // Use strategy instead of signal_source
                                    color={getSignalSourceColor(trade.strategy)}
                                    size="small"
                                    variant="outlined"
                                    title={`${getSignalSourceDisplay(trade.strategy)} - ${trade.exit_reason || 'No details available'}`}
                                  />
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="body2" fontWeight="bold">
                                    ${trade.entry_price?.toFixed(4) || '0.0000'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="body2" fontWeight="bold">
                                    ${trade.exit_price?.toFixed(4) || '0.0000'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography
                                    variant="body2"
                                    color={pnlColor}
                                    fontWeight="bold"
                                  >
                                    ${trade.pnl_usdt?.toFixed(2) || '0.00'}  {/* Use pnl_usdt */}
                                    <br />
                                    <Typography variant="caption" component="span">
                                      ({trade.pnl_pct?.toFixed(1)}%)
                                    </Typography>
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="body2" color="text.secondary">
                                    ${trade.fees_total?.toFixed(2) || '0.00'}  {/* Use fees_total */}
                                  </Typography>
                                </TableCell>
                                <TableCell align="right">
                                  <Typography variant="caption">
                                    {durationMinutes ? formatDuration(durationMinutes) : 'N/A'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="center">
                                  <Chip
                                    icon={isWin ? <CheckCircleIcon /> : <CloseIcon />}
                                    label={isWin ? 'WIN' : 'LOSS'}
                                    color={isWin ? 'success' : 'error'}
                                    size="small"
                                    variant="outlined"
                                  />
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                      No completed trades yet
                    </Typography>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Daily Performance Chart */}
        {performance?.daily_performance && performance.daily_performance.length > 0 ? (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  📈 Daily Learning Progress
                </Typography>
                <Grid container spacing={1}>
                  {performance.daily_performance.slice(-7).map((day, index) => (
                    <Grid item xs={12/7} key={index}>
                      <Box textAlign="center" p={1}>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(day.timestamp).toLocaleDateString('en-US', { weekday: 'short' })}
                        </Typography>
                        <Box
                          sx={{
                            height: 60,
                            display: 'flex',
                            alignItems: 'end',
                            justifyContent: 'center',
                            mb: 1
                          }}
                        >
                          <Box
                            sx={{
                              width: '80%',
                              height: `${Math.max(Math.abs(day.daily_pnl / 3), 10)}px`,
                              bgcolor: day.daily_pnl > 0 ? 'success.main' : day.daily_pnl < 0 ? 'error.main' : 'grey.300',
                              borderRadius: 1
                            }}
                          />
                        </Box>
                        <Typography
                          variant="caption"
                          fontWeight="bold"
                          color={day.daily_pnl > 0 ? 'success.main' : day.daily_pnl < 0 ? 'error.main' : 'text.secondary'}
                        >
                          ${day.daily_pnl?.toFixed(0)}
                        </Typography>
                        <br />
                        <Typography variant="caption" color="text.secondary">
                          {day.total_trades} trades
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        ) : (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  📈 Daily Learning Progress
                </Typography>
                <Box 
                  sx={{ 
                    textAlign: 'center', 
                    py: 4, 
                    color: 'text.secondary',
                    border: '2px dashed',
                    borderColor: 'divider',
                    borderRadius: 2
                  }}
                >
                  <Typography variant="body1" fontWeight="bold" gutterBottom>
                    No Trading Data Yet
                  </Typography>
                  <Typography variant="body2">
                    Start trading to see your daily performance progress here.
                    Charts will populate with real data as you trade.
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* ML Learning Insights */}
        {learningInsights && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
                  <AIIcon color="primary" />
                  Advanced ML Learning Analytics
                </Typography>
                
                <Grid container spacing={3}>
                  {/* Market Regime Learning */}
                  <Grid item xs={12} md={6}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight="bold" color="primary" gutterBottom>
                        🌊 Market Regime Detection
                      </Typography>
                      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                        Accuracy: {learningInsights.market_regime_learning?.regime_detection_accuracy}%
                      </Typography>
                      {learningInsights.market_regime_learning?.regimes_identified.map((regime, index) => (
                        <Chip
                          key={index}
                          label={regime.replace('_', ' ')}
                          variant="outlined"
                          size="small"
                          sx={{ mr: 1, mb: 1 }}
                        />
                      ))}
                    </Box>
                  </Grid>

                  {/* Strategy Adaptation */}
                  <Grid item xs={12} md={6}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight="bold" color="success.main" gutterBottom>
                        🔄 Strategy Adaptation
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Success Rate: {learningInsights.strategy_adaptation?.adaptation_success_rate}%
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Successful: {learningInsights.strategy_adaptation?.successful_adaptations} | 
                        Failed: {learningInsights.strategy_adaptation?.failed_adaptations}
                      </Typography>
                    </Box>
                  </Grid>

                  {/* Learning Metrics */}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2" fontWeight="bold" color="info.main" gutterBottom>
                      📊 Learning Improvement Metrics
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="success.main" fontWeight="bold">
                            +{learningInsights.signal_quality?.signal_confidence_improvement}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Signal Confidence
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="success.main" fontWeight="bold">
                            -{learningInsights.signal_quality?.false_positive_reduction}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            False Positives
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="primary.main" fontWeight="bold">
                            {learningInsights.risk_learning?.leverage_adjustment_accuracy}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Risk Accuracy
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="info.main" fontWeight="bold">
                            {learningInsights.signal_quality?.signal_timing_accuracy}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Timing Accuracy
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>
                  </Grid>

                  {/* AI Recommendations */}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2" fontWeight="bold" color="warning.main" gutterBottom>
                      🤖 AI Recommendations
                    </Typography>
                    {learningInsights.recommendations?.map((rec, index) => (
                      <Typography key={index} variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                        • {rec}
                      </Typography>
                    ))}
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Flow Trading Status Footer */}
      <Box mt={3} p={2} bgcolor="background.paper" borderRadius={2} border="1px solid" borderColor="divider">
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="body2" fontWeight="bold" display="flex" alignItems="center" gap={1}>
              {getStrategyIcon(currentStrategy)}
              Flow Trading Status - {availableStrategies[currentStrategy]?.name || 'Strategy'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Trading with real market conditions • Flow Trading only • Zero financial risk
            </Typography>
          </Box>
          <Box textAlign="right">
            <Typography variant="body2" color="primary" fontWeight="bold">
              Uptime: {status?.uptime_hours?.toFixed(1) || 0}h
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Strategy: {currentStrategy} • Trades: {status?.completed_trades || 0}
            </Typography>
          </Box>
        </Stack>
      </Box>
    </Box>
  );
};

export default PaperTrading;
