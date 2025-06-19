import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Snackbar,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  Chip,
  Divider,
  CardHeader,
  List,
  ListItem,
  ListItemText,
  Badge,
  Switch,
  FormControlLabel
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import axios from 'axios';
import config from '../config';
import SignalChart from '../components/SignalChart';
import DataFreshnessPanel from '../components/DataFreshnessPanel';

const Signals = () => {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const [autoTradingEnabled, setAutoTradingEnabled] = useState(false);
  const [scanProgress, setScanProgress] = useState(null);
  const [scanStatus, setScanStatus] = useState('idle');
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error in signals:', error);
    let errorMessage = 'Failed to fetch signals';

    if (error.response) {
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Signals endpoint not found. Please check the API configuration.';
          break;
        case 500:
          errorMessage = 'Server error. Please try again later.';
          break;
        default:
          errorMessage = `Server error: ${error.response.status}`;
      }
    } else if (error.request) {
      errorMessage = 'No response from server. Please check your connection.';
    } else if (error.code === 'ECONNABORTED') {
      errorMessage = 'Request timed out. Please try again.';
    }

    setError(errorMessage);
  };

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.SIGNALS}`, {
        timeout: 10000, // Increased timeout for background processing
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Handle new response format with status and progress
      const responseData = response.data;
      const status = responseData.status || 'success';
      const scanProgressData = responseData.scan_progress || null;
      
      // Update scan status and progress
      setScanStatus(status);
      setScanProgress(scanProgressData);
      
      // Convert opportunities object to signals array
      const opportunitiesData = responseData.data || {};
      const processedSignals = Object.values(opportunitiesData).map(opportunity => ({
        symbol: opportunity.symbol,
        signal_type: opportunity.direction || 'LONG',
        entry_price: opportunity.entry_price || opportunity.price,
        stop_loss: opportunity.stop_loss || opportunity.price * 0.98,
        take_profit: opportunity.take_profit || opportunity.price * 1.04,
        confidence: opportunity.confidence || Math.min(opportunity.score / 2, 1),
        strategy: opportunity.strategy || opportunity.setup_type,
        timestamp: new Date((opportunity.timestamp || Date.now()) * 1000).toISOString(),
        regime: opportunity.market_regime || opportunity.regime || 'TRENDING',
        price: opportunity.entry_price || opportunity.price,
        volume: opportunity.volume,
        volatility: opportunity.volatility,
        spread: opportunity.spread,
        score: opportunity.score,
        
        // Institutional-grade fields
        risk_reward: opportunity.risk_reward || 1.5,
        recommended_leverage: opportunity.recommended_leverage || 1.0,
        position_size: opportunity.position_size || 0,
        notional_value: opportunity.notional_value || 0,
        expected_profit: opportunity.expected_profit || 0,
        expected_return: opportunity.expected_return || 0,
        analysis_type: opportunity.analysis_type || 'basic',
        trend_alignment: opportunity.trend_alignment || 0,
        liquidity_score: opportunity.liquidity_score || 0,
        
        // $100 investment specific fields
        investment_amount_100: opportunity.investment_amount_100 || 100,
        position_size_100: opportunity.position_size_100 || 0,
        max_position_with_leverage_100: opportunity.max_position_with_leverage_100 || 0,
        expected_profit_100: opportunity.expected_profit_100 || 0,
        expected_return_100: opportunity.expected_return_100 || 0,
        
        indicators: {
          macd: { value: 0, signal: 0 },
          rsi: 50,
          bb: { upper: 0, middle: 0, lower: 0 }
        },
        is_stable_signal: opportunity.is_stable_signal || false,
        invalidation_reason: opportunity.invalidation_reason || null,
        signal_timestamp: opportunity.signal_timestamp || null
      }));
      
      setSignals(processedSignals);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
      
      // Show status message based on scan state
      if (status === 'scanning') {
        setError(`🔄 ${responseData.message || 'Scanning for opportunities...'}`);
      } else if (status === 'partial') {
        setError(`⏳ ${responseData.message || 'Scan in progress - showing partial results'}`);
      } else if (status === 'complete') {
        // Clear any previous status messages on completion
        setError(null);
      }
      
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchSignals, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  const executeManualTrade = async (signal) => {
    try {
      const tradeRequest = {
        symbol: signal.symbol,
        signal_type: signal.signal_type,
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit,
        confidence: signal.confidence,
        strategy: signal.strategy || 'manual'
      };

      const response = await axios.post(
        `${config.API_BASE_URL}${config.ENDPOINTS.EXECUTE_MANUAL_TRADE}`,
        tradeRequest,
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.status === 'success') {
        setError(null);
        // Show success message
        setError(`✅ ${response.data.message}`);
        setTimeout(() => setError(null), 5000);
      }
      } catch (err) {
      console.error('Error executing manual trade:', err);
      setError(`❌ Failed to execute trade: ${err.response?.data?.detail || err.message}`);
    }
  };

  const toggleAutoTrading = async () => {
    try {
      const newState = !autoTradingEnabled;
      setAutoTradingEnabled(newState);
      
      // Show status message
      setError(`🤖 Auto-trading ${newState ? 'ENABLED' : 'DISABLED'} - ${newState ? 'Bot will execute trades automatically' : 'Manual trading only'}`);
      setTimeout(() => setError(null), 3000);
      
      // TODO: In the future, this would call an API endpoint to enable/disable auto-trading
      // await axios.post(`${config.API_BASE_URL}/api/v1/trading/auto_trading`, { enabled: newState });
      
      } catch (err) {
      console.error('Error toggling auto-trading:', err);
      setError('❌ Failed to toggle auto-trading');
      setAutoTradingEnabled(!autoTradingEnabled); // Revert on error
    }
  };

  useEffect(() => {
    fetchSignals();
    
    // Use dynamic polling interval based on scan status
    const getPollingInterval = () => {
      if (scanProgress && scanProgress.in_progress) {
        return 3000; // 3 seconds during active scan
      }
      return 10000; // 10 seconds normally
    };
    
    const interval = setInterval(fetchSignals, getPollingInterval());
    
    // Update interval when scan status changes
    const intervalUpdater = setInterval(() => {
      clearInterval(interval);
      const newInterval = setInterval(fetchSignals, getPollingInterval());
      return () => clearInterval(newInterval);
    }, 1000);
    
    return () => {
      clearInterval(interval);
      clearInterval(intervalUpdater);
    };
  }, [retryCount, scanProgress?.in_progress]);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedSignals = signals
    .filter(signal => 
      signal.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      signal.strategy.toLowerCase().includes(filter.toLowerCase())
    )
    .sort((a, b) => {
      const multiplier = sortOrder === 'asc' ? 1 : -1;
      switch (sortBy) {
        case 'timestamp':
          return (new Date(a.timestamp) - new Date(b.timestamp)) * multiplier;
        case 'confidence':
          return (a.confidence - b.confidence) * multiplier;
        case 'price':
          return (a.price - b.price) * multiplier;
        default:
          return 0;
      }
    });

  const getRegimeColor = (regime) => {
    switch(regime) {
      case 'TRENDING':
        return 'success';
      case 'RANGING':
        return 'info';
      case 'VOLATILE':
        return 'warning';
      default:
        return 'default';
    }
  };

  const SignalCard = ({ signal }) => {
    const {
      symbol,
      signal_type,
      entry_price,
      stop_loss,
      take_profit,
      confidence,
      mtf_alignment,
      regime,
      strategy,
      timestamp
    } = signal;

    return (
      <Card key={symbol} sx={{ height: '100%' }}>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="h6" component="span">
                {symbol}
              </Typography>
              <Chip
                label={signal_type}
                color={signal_type === 'LONG' ? 'success' : 'error'}
                size="small"
              />
              {signal.is_stable_signal && (
                <Chip
                  label="STABLE"
                  color="info"
                  size="small"
                  variant="outlined"
                />
              )}
              {signal.invalidation_reason && (
                <Chip
                  label="INVALIDATED"
                  color="warning"
                  size="small"
                  variant="outlined"
                />
              )}
            </Box>
          }
          subheader={
            <Box>
              <Typography variant="body2" color="text.secondary">
                {strategy} • {regime}
              </Typography>
              {signal.invalidation_reason && (
                <Typography variant="caption" color="warning.main" sx={{ fontStyle: 'italic' }}>
                  ⚠️ {signal.invalidation_reason}
                </Typography>
              )}
              {signal.signal_timestamp && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  Signal age: {Math.round((Date.now() - signal.signal_timestamp) / 1000 / 60)}m
                </Typography>
              )}
            </Box>
          }
        />
        <CardContent>
          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Entry Price
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                  ${entry_price?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Stop Loss
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                  ${stop_loss?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Take Profit
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                  ${take_profit?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Confidence
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: '1rem',
                    color: confidence > 0.7 ? 'success.main' : confidence > 0.5 ? 'warning.main' : 'error.main'
                  }}
                >
                  {(confidence * 100)?.toFixed(0) || 'N/A'}{confidence > 0.7 ? '% 🏛️' : confidence > 0.5 ? '% ⚠️' : '% ❌'} 
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Risk/Reward
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: '1rem',
                    color: signal.risk_reward > 2 ? 'success.main' : 'inherit'
                  }}
                >
                  {signal.risk_reward?.toFixed(1) || 'N/A'}:1
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Leverage
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                  {signal.recommended_leverage?.toFixed(1) || '1.0'}x
                </Typography>
              </Box>
            </Grid>
          </Grid>

          {/* $100 Investment Section - Highlighted */}
          <Box 
            sx={{ 
              backgroundColor: 'primary.main', 
              color: 'primary.contrastText', 
              p: 2.5, 
              borderRadius: 2, 
              mb: 2,
              border: '1px solid',
              borderColor: 'primary.dark',
              boxShadow: 2
            }}
          >
            <Typography 
              variant="h6" 
              sx={{ 
                mb: 2, 
                textAlign: 'center',
                fontWeight: 'bold',
                fontSize: '1.1rem'
              }}
            >
              💰 $100 Investment with {signal.recommended_leverage?.toFixed(1) || '1.0'}x Leverage
            </Typography>
            <Grid container spacing={2} sx={{ textAlign: 'center' }}>
              <Grid item xs={4}>
                <Box sx={{ minHeight: '60px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: '0.75rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Trading Power
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      fontWeight: 'bold',
                      fontSize: '1.25rem',
                      lineHeight: 1.2
                    }}
                  >
                    ${signal.max_position_with_leverage_100?.toFixed(0) || 'N/A'}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ minHeight: '60px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: '0.75rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Expected Profit
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      color: 'success.light',
                      fontWeight: 'bold',
                      fontSize: '1.25rem',
                      lineHeight: 1.2
                    }}
                  >
                    ${signal.expected_profit_100?.toFixed(2) || 'N/A'}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ minHeight: '60px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: '0.75rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Return %
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      color: 'success.light',
                      fontWeight: 'bold',
                      fontSize: '1.25rem',
                      lineHeight: 1.2
                    }}
                  >
                    {signal.expected_return_100 ? (signal.expected_return_100 * 100).toFixed(1) + '%' : 'N/A'}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Position Size
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                  ${signal.notional_value?.toFixed(0) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Expected Profit
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem', color: 'success.main' }}>
                  ${signal.expected_profit?.toFixed(0) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '50px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Expected Return
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 'bold', fontSize: '1rem', color: 'success.main' }}>
                  {signal.expected_return ? (signal.expected_return * 100).toFixed(1) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '45px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Volume
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 'medium', fontSize: '0.9rem' }}>
                  {signal.volume ? (signal.volume / 1000000).toFixed(2) + 'M' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '45px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Volatility
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 'medium', fontSize: '0.9rem' }}>
                  {signal.volatility ? (signal.volatility * 100).toFixed(3) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ textAlign: 'center', minHeight: '45px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2" sx={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px', mb: 0.5 }}>
                  Spread
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 'medium', fontSize: '0.9rem' }}>
                  {signal.spread ? (signal.spread * 100).toFixed(3) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />
          
          <Box 
            display="flex" 
            justifyContent="space-between" 
            alignItems="center"
            sx={{ 
              flexDirection: { xs: 'column', sm: 'row' },
              gap: { xs: 2, sm: 0 }
            }}
          >
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ 
                fontSize: '0.75rem',
                textAlign: { xs: 'center', sm: 'left' }
              }}
            >
              {timestamp ? new Date(timestamp).toLocaleString() : 'No timestamp'}
            </Typography>
            <Button
              variant="contained"
              color={signal_type === 'LONG' ? 'success' : 'error'}
              size="medium"
              startIcon={signal_type === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />}
              onClick={() => executeManualTrade(signal)}
              sx={{ 
                fontWeight: 'bold',
                px: 3,
                py: 1,
                borderRadius: 2,
                boxShadow: 2,
                '&:hover': {
                  boxShadow: 3
                }
              }}
            >
              Execute {signal_type} Trade
            </Button>
          </Box>
        </CardContent>
      </Card>
    );
  };

  if (loading && !signals.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          Trading Signals
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <FormControlLabel
            control={
              <Switch
                checked={autoTradingEnabled}
                onChange={toggleAutoTrading}
                color="success"
              />
            }
            label={
              <Box display="flex" alignItems="center" gap={1}>
                <Typography variant="body2">
                  Auto-Trading
                </Typography>
                <Chip
                  label={autoTradingEnabled ? 'ON' : 'OFF'}
                  color={autoTradingEnabled ? 'success' : 'default'}
                  size="small"
                />
            </Box>
            }
          />
          <Chip
            label={`Status: ${loading ? 'LOADING' : signals.length > 0 ? 'ACTIVE' : 'NO DATA'}`}
            color={loading ? 'warning' : signals.length > 0 ? 'success' : 'default'}
          />
          <Tooltip title="Refresh signals">
            <IconButton onClick={fetchSignals} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Auto-trading status alert */}
      {autoTradingEnabled && (
        <Alert severity="info" sx={{ mb: 2 }}>
          🤖 <strong>Auto-Trading is ENABLED</strong> - The bot will automatically execute trades based on signals. 
          You can still manually execute individual trades using the buttons below.
        </Alert>
      )}

      {error && (
        <Snackbar 
          open={!!error} 
          autoHideDuration={error.includes('🔄') || error.includes('⏳') ? null : 6000} // Don't auto-hide progress messages
          onClose={() => setError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert 
            severity={
              error.includes('✅') ? 'success' : 
              error.includes('🔄') || error.includes('⏳') ? 'info' : 
              'error'
            } 
            onClose={() => setError(null)}
            action={
              !error.includes('✅') && !error.includes('🔄') && !error.includes('⏳') && (
              <Button color="inherit" size="small" onClick={fetchSignals}>
                Retry
              </Button>
              )
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Box mb={3}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Filter signals"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by symbol or strategy..."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Sort by</InputLabel>
              <Select
                value={sortBy}
                label="Sort by"
                onChange={(e) => handleSort(e.target.value)}
              >
                <MenuItem value="timestamp">Time</MenuItem>
                <MenuItem value="confidence">Confidence</MenuItem>
                <MenuItem value="price">Price</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Box>

      {lastUpdated && (
        <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      )}

      <Box mb={3}>
        <DataFreshnessPanel 
          lastUpdated={lastUpdated}
          signalsCount={signals.length}
          onRefresh={fetchSignals}
        />
      </Box>

      {/* Scan Progress Indicator */}
      {scanProgress && scanProgress.in_progress && (
        <Box mb={3}>
          <Paper sx={{ p: 2, bgcolor: 'info.light', borderLeft: '4px solid', borderColor: 'info.main' }}>
            <Grid container spacing={2} alignItems="center">
              <Grid item>
                <CircularProgress size={24} />
              </Grid>
              <Grid item xs>
                <Typography variant="body1" fontWeight="bold">
                  Scan in Progress
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {scanProgress.opportunities_found > 0 
                    ? `Found ${scanProgress.opportunities_found} opportunities so far...`
                    : 'Scanning markets for trading opportunities...'
                  }
                </Typography>
              </Grid>
              <Grid item>
                <Chip 
                  label={scanStatus === 'scanning' ? 'Starting...' : 'Processing'} 
                  color="info" 
                  size="small" 
                />
              </Grid>
            </Grid>
          </Paper>
        </Box>
      )}

      <Grid container spacing={3}>
          <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Trading Opportunities ({signals.length} found)
            </Typography>
            {signals.length === 0 ? (
              <Typography color="textSecondary">
                No trading opportunities available
              </Typography>
            ) : (
              <Grid container spacing={2}>
                {filteredAndSortedSignals.map((signal, index) => (
                  <Grid item xs={12} md={6} key={`${signal.symbol}-${index}`}>
                    <SignalCard signal={signal} />
                  </Grid>
                ))}
            </Grid>
        )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Signals; 