import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Paper,
  Stack,
  Divider,
  LinearProgress,
  Snackbar
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useMediaQuery } from '@mui/system';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Speed as SpeedIcon,
  MonetizationOn as ProfitIcon,
  AccountBalance as LeverageIcon,
  Timer as TimerIcon,
  Refresh as RefreshIcon,
  Assessment as AssessmentIcon,
  FlashOn as FlashIcon,
  PrecisionManufacturing as PrecisionIcon,
  TrendingFlat as ScalpIcon
} from '@mui/icons-material';
import axios from 'axios';
import config from '../config';

const Scalping = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [executedTrades, setExecutedTrades] = useState(new Set());
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [tradingStatus, setTradingStatus] = useState(null);

  useEffect(() => {
    fetchScalpingSignals();
    fetchTradingStatus();
    const interval = setInterval(fetchScalpingSignals, 60000); // Refresh every minute for scalping
    return () => clearInterval(interval);
  }, []);

  const fetchScalpingSignals = async () => {
    try {
      setLoading(signals.length === 0); // Only show loading on initial load
      const response = await axios.get(`${config.API_BASE_URL}/api/v1/trading/scalping-signals`);
      
      if (response.data.status === 'complete' || response.data.status === 'success') {
        setSignals(response.data.data || []);
        setSummary(response.data.summary || null);
        setError(null);
      } else if (response.data.status === 'no_signals') {
        setSignals([]);
        setSummary(null);
        setError(null);
      } else {
        setError(response.data.message || 'Failed to fetch scalping signals');
      }
    } catch (err) {
      setError('Failed to connect to scalping signals API');
      console.error('Error fetching scalping signals:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTradingStatus = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}/api/v1/trading/status`);
      if (response.data.status === 'success') {
        setTradingStatus(response.data.data);
      }
    } catch (error) {
      console.error('Error fetching trading status:', error);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await axios.post(`${config.API_BASE_URL}/api/v1/trading/refresh-scalping`);
      await fetchScalpingSignals();
    } catch (err) {
      setError('Failed to refresh scalping signals');
    } finally {
      setRefreshing(false);
    }
  };

  const handleEnterTrade = async (signal) => {
    setExecuting(true);
    
    try {
      const tradeRequest = {
        symbol: signal.symbol,
        signal_type: signal.direction,
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit,
        confidence: signal.confidence,
        strategy: signal.scalping_type || 'scalping'
      };

      const response = await fetch('/api/v1/trading/execute_manual_trade', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tradeRequest),
      });

      const result = await response.json();
      
      if (result.status === 'success') {
        setExecutedTrades(prev => new Set([...prev, signal.signal_id || signal.symbol]));
        setSnackbar({
          open: true,
          message: `Trade entered for ${signal.symbol}! ${result.message}`,
          severity: 'success'
        });
      } else {
        throw new Error(result.message || 'Trade execution failed');
      }
    } catch (error) {
      console.error('Error entering trade:', error);
      setSnackbar({
        open: true,
        message: `Failed to enter trade: ${error.message}`,
        severity: 'error'
      });
    } finally {
      setExecuting(false);
    }
  };

  const getDirectionColor = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return 'success';
      case 'short':
      case 'sell':
        return 'error';
      default:
        return 'default';
    }
  };

  const getDirectionIcon = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return <TrendingUpIcon />;
      case 'short':
      case 'sell':
        return <TrendingDownIcon />;
      default:
        return <ScalpIcon />;
    }
  };

  const getScalpingTypeColor = (type) => {
    switch(type) {
      case 'momentum_scalp':
        return 'primary';
      case 'mean_reversion_scalp':
        return 'secondary';
      case 'micro_breakout':
      case 'micro_breakdown':
        return 'warning';
      case 'volume_spike_scalp':
        return 'info';
      default:
        return 'default';
    }
  };

  const getScalpingTypeIcon = (type) => {
    switch(type) {
      case 'momentum_scalp':
        return <SpeedIcon />;
      case 'mean_reversion_scalp':
        return <PrecisionIcon />;
      case 'micro_breakout':
      case 'micro_breakdown':
        return <FlashIcon />;
      case 'volume_spike_scalp':
        return <AssessmentIcon />;
      default:
        return <ScalpIcon />;
    }
  };

  const CapitalReturnDisplay = ({ signal, compact = false }) => {
    const capitalReturn = signal.expected_capital_return_pct || 0;
    const leverage = signal.optimal_leverage || 1;
    const marketMove = signal.market_move_pct || 0;
    
    const getReturnColor = () => {
      if (capitalReturn >= 8) return 'success.main';
      if (capitalReturn >= 5) return 'warning.main';
      return 'info.main';
    };

    if (compact) {
      return (
        <Box sx={{ p: 1.5, bgcolor: 'background.paper', borderRadius: 1.5, border: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
            <Box textAlign="center">
              <Typography variant="h5" color={getReturnColor()} fontWeight="bold">
                {capitalReturn.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Capital Return
              </Typography>
            </Box>
            <Box textAlign="center">
              <Typography variant="h6" color="primary.main">
                {leverage.toFixed(1)}x
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Leverage
              </Typography>
            </Box>
            <Box textAlign="center">
              <Typography variant="h6" color="text.primary">
                {marketMove.toFixed(2)}%
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Market
              </Typography>
            </Box>
          </Stack>
        </Box>
      );
    }

    return (
      <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Stack spacing={2}>
          <Box textAlign="center">
            <Typography variant="h4" color={getReturnColor()} fontWeight="bold">
              {capitalReturn.toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Expected Capital Return
            </Typography>
          </Box>
          
          <Divider />
          
          <Grid container spacing={1}>
            <Grid item xs={6}>
              <Box textAlign="center">
                <Typography variant="h6" color="primary.main">
                  {leverage.toFixed(1)}x
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Leverage
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Box textAlign="center">
                <Typography variant="h6" color="text.primary">
                  {marketMove.toFixed(2)}%
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Market Move
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Stack>
      </Box>
    );
  };

  const ScalpingCard = ({ signal }) => {
    const entry = signal.entry_price || signal.entry || 0;
    const tp = signal.take_profit || 0;
    const sl = signal.stop_loss || 0;
    const confidence = signal.confidence || signal.confidence_score || 0;
    const capitalReturn = signal.expected_capital_return_pct || 0;
    const leverage = signal.optimal_leverage || 1;
    const marketMove = signal.market_move_pct || 0;
    const scalpType = signal.scalping_type || 'unknown';
    
    const riskReward = signal.risk_reward || 0;

    return (
      <Card 
        sx={{ 
          mb: 2, 
          borderRadius: 3, 
          boxShadow: 3,
          '&:hover': { boxShadow: 6 },
          border: '2px solid',
          borderColor: signal.status === 'stale' ? 'warning.main' : 
                      capitalReturn >= 7 ? 'success.main' : 'divider',
          bgcolor: signal.status === 'stale' ? 'warning.light' : 'background.paper',
          opacity: signal.status === 'stale' ? 0.9 : 1,
          position: 'relative'
        }}
      >
        {/* Priority Badge */}
        {capitalReturn >= 7 && (
          <Box 
            sx={{ 
              position: 'absolute', 
              top: 8, 
              right: 8, 
              zIndex: 1 
            }}
          >
            <Chip 
              icon={<FlashIcon />}
              label="HIGH PRIORITY" 
              color="error" 
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
          </Box>
        )}
        
        <CardContent sx={{ p: { xs: 1.5, sm: 2, md: 3 } }}>
          {/* Header */}
          <Box mb={1.5}>
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
              <Typography variant="h5" fontWeight="bold" color="primary">
                {signal.symbol}
              </Typography>
              <Chip
                icon={getScalpingTypeIcon(scalpType)}
                label={scalpType.replace('_', ' ').toUpperCase()}
                color={getScalpingTypeColor(scalpType)}
                size="small"
                variant="outlined"
                sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
              />
            </Box>
            <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
              <Chip
                icon={getDirectionIcon(signal.direction)}
                label={signal.direction}
                color={getDirectionColor(signal.direction)}
                size="small"
                sx={{ fontWeight: 'bold', fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
              />
              {/* Signal Status */}
              {signal.status === 'stale' && (
                <Chip
                  label={isMobile ? 'STALE' : `STALE (${(signal.drift_pct || 0).toFixed(2)}% drift)`}
                  color="warning"
                  size="small"
                  sx={{ fontWeight: 'bold', fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
                />
              )}
              {signal.status === 'active' && (
                <Chip
                  label="ACTIVE"
                  color="success"
                  size="small"
                  sx={{ fontWeight: 'bold', fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
                />
              )}
            </Box>
          </Box>

          {/* Capital Return Display */}
          <Box mb={2}>
            <CapitalReturnDisplay signal={signal} compact={isMobile} />
          </Box>

          {/* Price Levels */}
          <Grid container spacing={isMobile ? 1 : 2} mb={1.5}>
            <Grid item xs={4}>
              <Box textAlign="center" p={isMobile ? 0.5 : 1} bgcolor="background.default" borderRadius={1}>
                <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                  Entry
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" display="block">
                  ${entry.toFixed(isMobile ? 4 : 6)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box textAlign="center" p={isMobile ? 0.5 : 1} bgcolor="success.light" borderRadius={1}>
                <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                  TP
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" color="success.dark" display="block">
                  ${tp.toFixed(isMobile ? 4 : 6)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box textAlign="center" p={isMobile ? 0.5 : 1} bgcolor="error.light" borderRadius={1}>
                <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                  SL
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" color="error.dark" display="block">
                  ${sl.toFixed(isMobile ? 4 : 6)}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          {/* Metrics Row */}
          <Stack direction="row" spacing={isMobile ? 1 : 2} justifyContent="space-between" mb={1.5}>
            <Box textAlign="center">
              <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                Confidence
              </Typography>
              <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" display="block">
                {(confidence * 100).toFixed(1)}%
              </Typography>
            </Box>
            <Box textAlign="center">
              <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                R:R
              </Typography>
              <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" color={riskReward >= 2 ? 'success.main' : 'text.primary'} display="block">
                {riskReward.toFixed(2)}:1
              </Typography>
            </Box>
            <Box textAlign="center">
              <Typography variant="caption" color="textSecondary" fontSize={isMobile ? '0.65rem' : undefined}>
                Time
              </Typography>
                              <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold" color="primary.main" display="block">
                  {signal.timeframe || '15m/1h'}
                </Typography>
            </Box>
          </Stack>

          {/* Capital Scenarios */}
          {!isMobile && (
            <Box p={2} bgcolor="background.default" borderRadius={2} mb={2}>
              <Typography variant="subtitle2" color="primary" gutterBottom>
                💰 Capital Scenarios
              </Typography>
              <Grid container spacing={1}>
                {['capital_100', 'capital_500', 'capital_1000', 'capital_5000'].map((key) => {
                  const scenario = signal[key] || {};
                  return (
                    <Grid item xs={6} sm={3} key={key}>
                      <Box textAlign="center">
                        <Typography variant="body2" fontWeight="bold">
                          ${scenario.capital || key.split('_')[1]}
                        </Typography>
                        <Typography variant="caption" color="success.main">
                          → ${(scenario.expected_profit || 0).toFixed(0)}
                        </Typography>
                      </Box>
                    </Grid>
                  );
                })}
              </Grid>
            </Box>
          )}

          {/* Mobile Quick Scenarios */}
          {isMobile && (
            <Box p={1} bgcolor="background.default" borderRadius={1} mb={1.5}>
              <Stack direction="row" spacing={1} justifyContent="space-between">
                {[100, 500, 1000].map((capital) => {
                  const scenario = signal[`capital_${capital}`] || {};
                  return (
                    <Box textAlign="center" key={capital}>
                      <Typography variant="caption" fontWeight="bold" fontSize="0.65rem">
                        ${capital}
                      </Typography>
                      <Typography variant="caption" color="success.main" display="block" fontSize="0.65rem">
                        ${(scenario.expected_profit || 0).toFixed(0)}
                      </Typography>
                    </Box>
                  );
                })}
              </Stack>
            </Box>
          )}

          {/* Action Buttons */}
          <Box display="flex" gap={1} mt={2}>
            <Button
              variant="contained"
              color={signal.direction === 'LONG' ? 'success' : 'error'}
              size="small"
              startIcon={executing ? <CircularProgress size={16} color="inherit" /> : getDirectionIcon(signal.direction)}
              onClick={() => handleEnterTrade(signal)}
              disabled={executing || executedTrades.has(signal.signal_id || signal.symbol)}
              sx={{ 
                flex: 1,
                fontWeight: 'bold',
                opacity: executedTrades.has(signal.signal_id || signal.symbol) ? 0.6 : 1
              }}
            >
              {executedTrades.has(signal.signal_id || signal.symbol) 
                ? 'Trade Entered' 
                : executing 
                  ? 'Entering...' 
                  : `Enter ${signal.direction} Trade`
              }
            </Button>
            
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setSelectedSignal(signal);
                setDetailsOpen(true);
              }}
              sx={{ minWidth: 'auto', px: 2 }}
            >
              Details
            </Button>
          </Box>

          {/* Timestamp */}
          {signal.timestamp && !isMobile && (
            <Typography variant="caption" color="textSecondary" display="block" textAlign="center" mt={1}>
              {new Date(signal.timestamp).toLocaleString()}
            </Typography>
          )}
        </CardContent>
      </Card>
    );
  };

  const ScalpingDetails = ({ signal, open, onClose }) => {
    if (!signal) return null;

    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <ScalpIcon color="primary" />
            <Typography variant="h6">
              Scalping Details: {signal.symbol}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3}>
            {/* Capital Return Analysis */}
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" color="primary" gutterBottom>
                Capital Return Analysis
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <CapitalReturnDisplay signal={signal} />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Trade Calculation:</Typography>
                    <Typography variant="body2" color="textSecondary">
                      • Market Move: {(signal.market_move_pct || 0).toFixed(2)}%
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      • Leverage: {(signal.optimal_leverage || 1).toFixed(1)}x
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      • Capital Return: {(signal.expected_capital_return_pct || 0).toFixed(1)}%
                    </Typography>
                    <Typography variant="body2" color="primary" sx={{ mt: 1, fontWeight: 'bold' }}>
                      Formula: {(signal.market_move_pct || 0).toFixed(2)}% × {(signal.optimal_leverage || 1).toFixed(1)}x = {(signal.expected_capital_return_pct || 0).toFixed(1)}%
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            {/* Signal Details */}
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" color="primary" gutterBottom>
                Signal Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Type:</Typography>
                  <Typography variant="body1">{signal.scalping_type?.replace('_', ' ') || 'Unknown'}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Timeframe:</Typography>
                  <Typography variant="body1">{signal.timeframe || '15m/1h'}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Volume Surge:</Typography>
                  <Typography variant="body1">{(signal.volume_surge || 1).toFixed(2)}x</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Volatility:</Typography>
                  <Typography variant="body1">{(signal.volatility || 0).toFixed(2)}%</Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* Reasoning */}
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" color="primary" gutterBottom>
                Analysis Reasoning
              </Typography>
              {signal.reasoning && signal.reasoning.map((reason, index) => (
                <Typography key={index} variant="body2" color="textSecondary" gutterBottom>
                  • {reason}
                </Typography>
              ))}
            </Paper>

            {/* Position Sizing */}
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" color="primary" gutterBottom>
                Position Sizing Scenarios
              </Typography>
              <Grid container spacing={2}>
                {['capital_100', 'capital_500', 'capital_1000', 'capital_5000'].map((key) => {
                  const scenario = signal[key] || {};
                  return (
                    <Grid item xs={12} sm={6} md={3} key={key}>
                      <Box p={2} bgcolor="background.default" borderRadius={2}>
                        <Typography variant="subtitle2" color="primary" textAlign="center">
                          ${scenario.capital || key.split('_')[1]} Capital
                        </Typography>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="body2" color="textSecondary">
                          Position: {(scenario.position_size || 0).toFixed(4)}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Value: ${(scenario.position_value || 0).toFixed(0)}
                        </Typography>
                        <Typography variant="body2" color="success.main" fontWeight="bold">
                          Profit: ${(scenario.expected_profit || 0).toFixed(0)}
                        </Typography>
                        <Typography variant="body2" color="error.main">
                          Risk: ${(scenario.risk_amount || 0).toFixed(0)}
                        </Typography>
                      </Box>
                    </Grid>
                  );
                })}
              </Grid>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box sx={{ p: { xs: 0.5, sm: 2, md: 3 }, maxWidth: '100vw', overflow: 'hidden' }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={isMobile ? 2 : 3} px={isMobile ? 1 : 0}>
        <Box>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant={isMobile ? "h5" : "h4"} color="primary">
              Precision Scalping
            </Typography>
            {tradingStatus && (
              <Chip
                label={tradingStatus.trading_mode}
                color={tradingStatus.real_trading_enabled ? 'success' : 'warning'}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 'bold' }}
              />
            )}
          </Box>
          <Typography variant={isMobile ? "body2" : "body1"} color="textSecondary">
            {isMobile ? '3-10% Capital Returns' : '3-10% Capital Returns via Precise Leverage • 15m/1h Timeframes'}
          </Typography>
          {tradingStatus && !tradingStatus.real_trading_enabled && (
            <Typography variant="caption" color="warning.main" display="block" mt={0.5}>
              ⚠️ Simulation Mode Active - No real money at risk
            </Typography>
          )}
        </Box>
        <Button
          variant="outlined"
          startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={handleRefresh}
          disabled={refreshing}
          size={isMobile ? "small" : "medium"}
        >
          {isMobile ? (refreshing ? '...' : 'Refresh') : (refreshing ? 'Refreshing...' : 'Refresh')}
        </Button>
      </Box>

      {/* Summary Stats */}
      {summary && (
        <Paper sx={{ p: { xs: 1.5, sm: 2, md: 3 }, mb: { xs: 2, sm: 3 }, mx: { xs: 1, sm: 0 } }}>
          <Typography variant={isMobile ? "subtitle1" : "h6"} color="primary" gutterBottom>
            Scalping Summary
          </Typography>
          <Grid container spacing={isMobile ? 2 : 3}>
            <Grid item xs={6} md={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h6" : "h5"} color="primary.main">
                  {summary.total_signals}
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} color="textSecondary">
                  {isMobile ? 'Signals' : 'Active Signals'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} md={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h6" : "h5"} color="success.main">
                  {summary.avg_capital_return_pct}%
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} color="textSecondary">
                  {isMobile ? 'Avg Return' : 'Avg Capital Return'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} md={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h6" : "h5"} color="warning.main">
                  {summary.avg_optimal_leverage}x
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} color="textSecondary">
                  {isMobile ? 'Leverage' : 'Avg Leverage'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} md={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h6" : "h5"} color="info.main">
                  15m
                </Typography>
                <Typography variant={isMobile ? "caption" : "body2"} color="textSecondary">
                  Timeframe
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: { xs: 2, sm: 3 }, mx: { xs: 1, sm: 0 } }}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight={isMobile ? "200px" : "300px"}>
          <CircularProgress size={isMobile ? 40 : 60} />
        </Box>
      )}

      {/* No Signals */}
      {!loading && signals.length === 0 && (
        <Paper sx={{ p: { xs: 2, sm: 4 }, textAlign: 'center', mx: { xs: 1, sm: 0 } }}>
          <ScalpIcon sx={{ fontSize: { xs: 48, sm: 64 }, color: 'text.secondary', mb: 2 }} />
          <Typography variant={isMobile ? "subtitle1" : "h6"} color="textSecondary" gutterBottom>
            No Scalping Opportunities
          </Typography>
          <Typography variant="body2" color="textSecondary">
            {isMobile ? 'Waiting for scalping setups' : 'Waiting for precision scalping setups targeting 3-10% capital returns'}
          </Typography>
        </Paper>
      )}

      {/* Signals Grid */}
      {!loading && signals.length > 0 && (
        <Box px={isMobile ? 1 : 0}>
          <Grid container spacing={isMobile ? 1 : 2}>
            {signals.map((signal, index) => (
              <Grid item xs={12} sm={12} md={6} lg={4} xl={4} key={signal.signal_id || index}>
                <ScalpingCard signal={signal} />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Details Dialog */}
      <ScalpingDetails 
        signal={selectedSignal} 
        open={detailsOpen} 
        onClose={() => setDetailsOpen(false)} 
      />

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setSnackbar({ ...snackbar, open: false })} 
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Scalping; 