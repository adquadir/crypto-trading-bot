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
  Snackbar,
  Container,
  useMediaQuery,
  useTheme
} from '@mui/material';
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
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));
  
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState(null);
  const [executingSignals, setExecutingSignals] = useState(new Set());
  const [executedTrades, setExecutedTrades] = useState(new Set());
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [tradingStatus, setTradingStatus] = useState(null);
  const [enteringAllTrades, setEnteringAllTrades] = useState(false);

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
    const signalId = signal.signal_id || signal.symbol;
    setExecutingSignals(prev => new Set([...prev, signalId]));
    
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

      const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.EXECUTE_MANUAL_TRADE}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tradeRequest),
      });

      const result = await response.json();
      
      if (result.status === 'success') {
        setExecutedTrades(prev => new Set([...prev, signalId]));
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
      setExecutingSignals(prev => {
        const newSet = new Set(prev);
        newSet.delete(signalId);
        return newSet;
      });
    }
  };

  const handleEnterAllTrades = async () => {
    setEnteringAllTrades(true);
    try {
      const response = await axios.post(`${config.API_BASE_URL}/api/v1/trading/enter-all-trades`);
      
      if (response.data.status === 'success') {
        const { entered_trades, failed_trades, total_expected_capital, avg_expected_return } = response.data.data;
        
        // Mark all entered trades as executed
        const enteredSymbols = response.data.data.entered_details.map(trade => trade.symbol);
        setExecutedTrades(prev => new Set([...prev, ...enteredSymbols]));
        
        setSnackbar({
          open: true,
          message: `🎯 Bulk Entry Complete! ${entered_trades} trades entered, ${failed_trades} failed. Expected capital: $${total_expected_capital.toFixed(0)}, Avg return: ${avg_expected_return.toFixed(1)}%`,
          severity: 'success'
        });
      } else {
        throw new Error(response.data.message || 'Bulk entry failed');
      }
    } catch (error) {
      console.error('Error entering all trades:', error);
      setSnackbar({
        open: true,
        message: `Failed to enter all trades: ${error.message}`,
        severity: 'error'
      });
    } finally {
      setEnteringAllTrades(false);
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
    const scalpType = signal.scalping_type || 'unknown';
    const riskReward = signal.risk_reward || 0;

    return (
      <Card 
        sx={{ 
          mb: 1.5, 
          borderRadius: 2, 
          boxShadow: 2,
          '&:hover': { boxShadow: 4 },
          border: '1px solid',
          borderColor: signal.status === 'stale' ? 'warning.main' : 
                      capitalReturn >= 7 ? 'success.main' : 'divider',
          bgcolor: signal.status === 'stale' ? 'warning.light' : 'background.paper',
          opacity: signal.status === 'stale' ? 0.9 : 1,
          position: 'relative'
        }}
      >
        <CardContent sx={{ p: { xs: 1, sm: 1.5 }, '&:last-child': { pb: { xs: 1, sm: 1.5 } } }}>
          {/* Compact Header */}
          <Box mb={1}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
              <Typography variant="h6" fontWeight="bold" color="primary">
                {signal.symbol}
              </Typography>
              <Stack direction="row" spacing={0.5} alignItems="center">
                {capitalReturn >= 7 && (
                  <Chip 
                    icon={<FlashIcon fontSize="small" />}
                    label="HIGH" 
                    color="error" 
                    size="small"
                    sx={{ fontWeight: 'bold', fontSize: '0.6rem', height: '20px' }}
                  />
                )}
                <Chip
                  icon={getDirectionIcon(signal.direction)}
                  label={signal.direction}
                  color={getDirectionColor(signal.direction)}
                  size="small"
                  sx={{ fontWeight: 'bold', fontSize: '0.65rem', height: '24px' }}
                />
              </Stack>
            </Box>
            
            {/* Key Metrics in One Row */}
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" gap={0.5}>
              <Chip
                label={`${(capitalReturn).toFixed(1)}%`}
                color={capitalReturn >= 7 ? 'success' : capitalReturn >= 5 ? 'warning' : 'info'}
                size="small"
                sx={{ fontWeight: 'bold', fontSize: '0.65rem', height: '20px' }}
              />
              <Chip
                label={`${(confidence * 100).toFixed(0)}%`}
                variant="outlined"
                size="small"
                sx={{ fontSize: '0.65rem', height: '20px' }}
              />
              <Chip
                label={`${riskReward.toFixed(1)}:1`}
                variant="outlined"
                color={riskReward >= 2 ? 'success' : 'default'}
                size="small"
                sx={{ fontSize: '0.65rem', height: '20px' }}
              />
              <Chip
                icon={getScalpingTypeIcon(scalpType)}
                label={scalpType.replace('_', ' ').toUpperCase()}
                color={getScalpingTypeColor(scalpType)}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.6rem', height: '20px' }}
              />
              {signal.status === 'stale' && (
                <Chip
                  label="STALE"
                  color="warning"
                  size="small"
                  sx={{ fontSize: '0.65rem', height: '20px' }}
                />
              )}
            </Stack>
          </Box>

          {/* Compact Price Levels */}
          <Box mb={1}>
            <Grid container spacing={0.5}>
              <Grid item xs={4}>
                <Box textAlign="center" p={0.5} bgcolor="background.default" borderRadius={1}>
                  <Typography variant="caption" color="textSecondary" fontSize="0.6rem">
                    Entry
                  </Typography>
                  <Typography variant="caption" fontWeight="bold" display="block" fontSize="0.7rem">
                    ${entry.toFixed(4)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box textAlign="center" p={0.5} bgcolor="success.light" borderRadius={1}>
                  <Typography variant="caption" color="textSecondary" fontSize="0.6rem">
                    TP
                  </Typography>
                  <Typography variant="caption" fontWeight="bold" color="success.dark" display="block" fontSize="0.7rem">
                    ${tp.toFixed(4)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box textAlign="center" p={0.5} bgcolor="error.light" borderRadius={1}>
                  <Typography variant="caption" color="textSecondary" fontSize="0.6rem">
                    SL
                  </Typography>
                  <Typography variant="caption" fontWeight="bold" color="error.dark" display="block" fontSize="0.7rem">
                    ${sl.toFixed(4)}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>



          {/* Compact Action Buttons */}
          <Stack direction="row" spacing={0.5}>
            <Button
              variant="contained"
              color={signal.direction === 'LONG' ? 'success' : 'error'}
              size="small"
              startIcon={executingSignals.has(signal.signal_id || signal.symbol) ? <CircularProgress size={12} color="inherit" /> : getDirectionIcon(signal.direction)}
              onClick={() => handleEnterTrade(signal)}
              disabled={executingSignals.has(signal.signal_id || signal.symbol) || executedTrades.has(signal.signal_id || signal.symbol)}
              sx={{ 
                flex: 1,
                fontWeight: 'bold',
                fontSize: '0.7rem',
                py: 0.5,
                opacity: executedTrades.has(signal.signal_id || signal.symbol) ? 0.6 : 1
              }}
            >
              {executedTrades.has(signal.signal_id || signal.symbol) 
                ? 'Entered' 
                : executingSignals.has(signal.signal_id || signal.symbol) 
                  ? 'Entering...' 
                  : `${signal.direction}`
              }
            </Button>
            
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setSelectedSignal(signal);
                setDetailsOpen(true);
              }}
              sx={{ minWidth: '60px', px: 1, fontSize: '0.7rem', py: 0.5 }}
            >
              Info
            </Button>
          </Stack>

          {/* Compact Timestamp */}
          {signal.timestamp && (
            <Typography variant="caption" color="textSecondary" display="block" textAlign="center" mt={0.5} fontSize="0.6rem">
              {new Date(signal.timestamp).toLocaleTimeString()}
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

  if (loading && signals.length === 0) {
    return (
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress size={isMobile ? 40 : 60} />
          {!isMobile && (
            <Typography variant="h6" sx={{ ml: 2 }}>
              Loading scalping signals...
            </Typography>
          )}
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: { xs: 1, sm: 2, md: 3 } }}>
      {/* Mobile-Optimized Header */}
      <Box 
        display="flex" 
        flexDirection={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between" 
        alignItems={{ xs: 'stretch', sm: 'center' }} 
        mb={{ xs: 2, sm: 3 }}
        gap={{ xs: 2, sm: 0 }}
      >
        <Box>
          <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold" gutterBottom>
            ⚡ High-Speed Scalping
          </Typography>
          <Typography 
            variant="body1" 
            color="text.secondary"
            sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}
          >
            Rapid-fire 15m/1h precision signals for quick profits
          </Typography>
        </Box>
        
        {/* Mobile-Optimized Action Buttons */}
        <Stack 
          direction={{ xs: 'column', sm: 'row' }} 
          spacing={1}
          alignItems={{ xs: 'stretch', sm: 'center' }}
        >
          <Button
            variant="contained"
            color="primary"
            onClick={handleEnterAllTrades}
            disabled={enteringAllTrades || signals.length === 0}
            startIcon={enteringAllTrades ? <CircularProgress size={16} /> : <SpeedIcon />}
            size={isMobile ? "medium" : "small"}
            sx={{ 
              minHeight: { xs: '44px', sm: 'auto' },
              fontSize: { xs: '0.875rem', sm: '0.75rem' }
            }}
          >
            {enteringAllTrades ? 'Entering...' : `Enter All ${signals.length} Trades`}
          </Button>
          
          <Button
            variant="outlined"
            onClick={handleRefresh}
            disabled={refreshing}
            startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
            size={isMobile ? "medium" : "small"}
            sx={{ 
              minHeight: { xs: '44px', sm: 'auto' },
              fontSize: { xs: '0.875rem', sm: '0.75rem' }
            }}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Stack>
      </Box>

      {/* Summary Stats - Mobile Optimized */}
      {summary && (
        <Paper 
          sx={{ 
            p: { xs: 2, sm: 3 }, 
            mb: { xs: 2, sm: 3 },
            background: 'linear-gradient(135deg, rgba(255, 152, 0, 0.1) 0%, rgba(244, 67, 54, 0.1) 100%)'
          }}
        >
          <Typography variant="h6" gutterBottom fontWeight="bold">
            📊 Scalping Overview
          </Typography>
          <Grid container spacing={{ xs: 2, sm: 3 }}>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold" color="primary.main">
                  {summary.total_signals || 0}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Active Signals
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold" color="success.main">
                  {(summary.avg_expected_return || 0).toFixed(1)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Avg Expected Return
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold" color="warning.main">
                  ${(summary.total_expected_capital || 0).toFixed(0)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Total Expected Capital
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold" color="info.main">
                  {(summary.high_priority_count || 0)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  High Priority
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Trading Status */}
      {tradingStatus && (
        <Alert 
          severity={tradingStatus.auto_trading_enabled ? "success" : "info"} 
          sx={{ mb: { xs: 2, sm: 3 } }}
        >
          <Typography variant="body2">
            <strong>Trading Mode:</strong> {tradingStatus.trading_mode} | 
            <strong> Auto Trading:</strong> {tradingStatus.auto_trading_enabled ? 'ON' : 'OFF'} | 
            <strong> Available Balance:</strong> ${tradingStatus.available_balance?.toFixed(2) || '0.00'}
          </Typography>
        </Alert>
      )}

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: { xs: 2, sm: 3 } }}>
          {error}
        </Alert>
      )}

      {/* Signals Grid */}
      {signals.length === 0 ? (
        <Paper sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No scalping signals available
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Check back in a few minutes for new high-speed opportunities
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }}>
          {signals
            .sort((a, b) => {
              // Sort by timestamp descending (newest first)
              const timestampA = new Date(a.timestamp || 0).getTime();
              const timestampB = new Date(b.timestamp || 0).getTime();
              return timestampB - timestampA;
            })
            .map((signal, index) => (
              <Grid item xs={12} sm={6} lg={4} key={`${signal.symbol}-${index}`}>
                <ScalpingCard signal={signal} />
              </Grid>
            ))}
        </Grid>
      )}

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          severity={snackbar.severity} 
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Signal Details Dialog */}
      <ScalpingDetails 
        signal={selectedSignal} 
        open={detailsOpen} 
        onClose={() => setDetailsOpen(false)} 
      />
    </Container>
  );
};

export default Scalping; 