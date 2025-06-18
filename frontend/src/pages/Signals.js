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
        timeout: 5000,
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Convert opportunities object to signals array
      const opportunitiesData = response.data.data || {};
      const processedSignals = Object.values(opportunitiesData).map(opportunity => ({
        symbol: opportunity.symbol,
        signal_type: 'LONG', // Default to LONG for now
        entry_price: opportunity.price,
        stop_loss: opportunity.price * 0.98, // 2% stop loss
        take_profit: opportunity.price * 1.04, // 4% take profit
        confidence: Math.min(opportunity.score / 2, 1), // Convert score to confidence
        strategy: opportunity.strategy,
        timestamp: new Date(opportunity.timestamp * 1000).toISOString(),
        regime: 'TRENDING', // Default regime
        price: opportunity.price,
        volume: opportunity.volume,
        volatility: opportunity.volatility,
        spread: opportunity.spread,
        score: opportunity.score,
        indicators: {
          macd: { value: 0, signal: 0 },
          rsi: 50,
          bb: { upper: 0, middle: 0, lower: 0 }
        }
      }));
      
      setSignals(processedSignals);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
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
    const interval = setInterval(fetchSignals, 10000); // Poll every 10 seconds
    return () => clearInterval(interval);
  }, [retryCount]);

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
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6" component="h2">
              {symbol}
            </Typography>
            <Chip
              label={signal_type}
              color={signal_type === 'LONG' ? 'success' : 'error'}
              icon={signal_type === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />}
            />
          </Box>
          
          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Entry Price
              </Typography>
              <Typography variant="body1">
                ${entry_price?.toFixed(2) || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Stop Loss
              </Typography>
              <Typography variant="body1">
                ${stop_loss?.toFixed(2) || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Take Profit
              </Typography>
              <Typography variant="body1">
                ${take_profit?.toFixed(2) || 'N/A'}
              </Typography>
            </Grid>
          </Grid>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Confidence
              </Typography>
              <Typography variant="body1">
                {confidence?.toFixed(2) || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Strategy
              </Typography>
              <Typography variant="body1">
                {strategy || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Score
              </Typography>
              <Typography variant="body1">
                {signal.score?.toFixed(1) || 'N/A'}
              </Typography>
            </Grid>
          </Grid>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Volume
              </Typography>
              <Typography variant="body1">
                {signal.volume ? (signal.volume / 1000000).toFixed(2) + 'M' : 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Volatility
              </Typography>
              <Typography variant="body1">
                {signal.volatility ? (signal.volatility * 100).toFixed(3) + '%' : 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography color="textSecondary" variant="body2">
                Spread
              </Typography>
              <Typography variant="body1">
                {signal.spread ? (signal.spread * 100).toFixed(3) + '%' : 'N/A'}
              </Typography>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />
          
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="caption" color="textSecondary">
              {timestamp ? new Date(timestamp).toLocaleString() : 'No timestamp'}
            </Typography>
            <Button
              variant="contained"
              color={signal_type === 'LONG' ? 'success' : 'error'}
              size="small"
              startIcon={signal_type === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />}
              onClick={() => executeManualTrade(signal)}
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
          autoHideDuration={6000} 
          onClose={() => setError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert 
            severity={error.includes('✅') ? 'success' : 'error'} 
            onClose={() => setError(null)}
            action={
              !error.includes('✅') && (
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