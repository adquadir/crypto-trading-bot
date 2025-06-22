import React, { useState, useEffect } from 'react';
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
  Stack,
  Divider
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import WarningIcon from '@mui/icons-material/Warning';
import axios from 'axios';
import config from '../config';

const Positions = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('unrealized_pnl');
  const [sortOrder, setSortOrder] = useState('desc');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [tradingStatus, setTradingStatus] = useState(null);
  const [positionsSummary, setPositionsSummary] = useState(null);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error fetching positions:', error);
    let errorMessage = 'Failed to fetch positions';

    if (error.response) {
      // Server responded with error
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Positions endpoint not found. Please check the API configuration.';
          break;
        case 500:
          errorMessage = 'Server error. Please try again later.';
          break;
        default:
          errorMessage = `Server error: ${error.response.status}`;
      }
    } else if (error.request) {
      // Request made but no response
      errorMessage = 'No response from server. Please check your connection.';
    } else if (error.code === 'ECONNABORTED') {
      errorMessage = 'Request timed out. Please try again.';
    }

    setError(errorMessage);
  };

  const fetchPositions = async () => {
    try {
      setLoading(true);
      
      // Fetch positions
      const positionsResponse = await axios.get(`${config.API_BASE_URL}/api/v1/trading/positions`, {
        timeout: 5000
      });
      
      // Fetch trading status
      const statusResponse = await axios.get(`${config.API_BASE_URL}/api/v1/trading/status`, {
        timeout: 5000
      });
      
      if (positionsResponse.data.status === 'success') {
        setPositions(positionsResponse.data.data || []);
        setPositionsSummary(positionsResponse.data.summary);
      }
      
      if (statusResponse.data.status === 'success') {
        setTradingStatus(statusResponse.data.data);
      }
      
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchPositions, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000); // Refresh every 10 seconds
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

  const filteredAndSortedPositions = positions
    .filter(position => 
      position.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      position.side.toLowerCase().includes(filter.toLowerCase()) ||
      position.strategy?.toLowerCase().includes(filter.toLowerCase())
    )
    .sort((a, b) => {
      const multiplier = sortOrder === 'asc' ? 1 : -1;
      switch (sortBy) {
        case 'unrealized_pnl':
          return ((a.unrealized_pnl || 0) - (b.unrealized_pnl || 0)) * multiplier;
        case 'size':
          return ((a.size || 0) - (b.size || 0)) * multiplier;
        case 'leverage':
          return ((a.leverage || 0) - (b.leverage || 0)) * multiplier;
        case 'unrealized_pnl_percent':
          return ((a.unrealized_pnl_percent || 0) - (b.unrealized_pnl_percent || 0)) * multiplier;
        default:
          return 0;
      }
    });

  const getTotalPnL = () => {
    return positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
  };

  const getPositionIcon = (side) => {
    return side === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />;
  };

  const getPositionColor = (side) => {
    return side === 'LONG' ? 'success' : 'error';
  };

  if (loading && !positions.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant="h4">
              Trading Positions
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
          {tradingStatus && !tradingStatus.real_trading_enabled && (
            <Typography variant="caption" color="warning.main">
              <WarningIcon fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
              Simulation Mode Active - Demo positions only
            </Typography>
          )}
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <Tooltip title="Refresh positions">
            <IconButton onClick={fetchPositions} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Summary Cards */}
      {positionsSummary && (
        <Grid container spacing={2} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="primary">
                  {positionsSummary.total_positions}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Total Positions
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="success.main">
                  {positionsSummary.open_positions}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Open Positions
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography 
                  variant="h6" 
                  color={positionsSummary.total_unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
                >
                  ${positionsSummary.total_unrealized_pnl?.toFixed(2)}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Total PnL
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="primary">
                  {tradingStatus?.account_balance?.toFixed(0) || 'N/A'}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Account Balance
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {error && (
        <Snackbar 
          open={!!error} 
          autoHideDuration={6000} 
          onClose={() => setError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert 
            severity="error" 
            onClose={() => setError(null)}
            action={
              <Button color="inherit" size="small" onClick={fetchPositions}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      {/* Filters and Sorting */}
      <Box mb={3}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Filter positions"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by symbol, side, or strategy..."
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
                <MenuItem value="unrealized_pnl">Unrealized PnL</MenuItem>
                <MenuItem value="unrealized_pnl_percent">PnL %</MenuItem>
                <MenuItem value="size">Position Size</MenuItem>
                <MenuItem value="leverage">Leverage</MenuItem>
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

      {/* Positions Grid */}
      <Grid container spacing={3}>
        {filteredAndSortedPositions.length === 0 ? (
          <Grid item xs={12}>
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <ShowChartIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="textSecondary" gutterBottom>
                {positions.length === 0 ? 'No Active Positions' : 'No positions match your filter'}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                {positions.length === 0 
                  ? 'Start trading by entering signals from the Scalping page' 
                  : 'Try adjusting your search criteria'
                }
              </Typography>
            </Paper>
          </Grid>
        ) : (
          filteredAndSortedPositions.map((position, index) => (
            <Grid item xs={12} sm={6} md={4} key={position.position_id || index}>
              <Card sx={{ 
                border: position.type === 'simulated' ? '2px dashed' : '1px solid',
                borderColor: position.type === 'simulated' ? 'warning.main' : 'divider'
              }}>
                <CardContent>
                  {/* Header */}
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6">{position.symbol}</Typography>
                    <Box display="flex" gap={0.5}>
                      <Chip
                        icon={getPositionIcon(position.side)}
                        label={position.side}
                        color={getPositionColor(position.side)}
                        size="small"
                        sx={{ fontWeight: 'bold' }}
                      />
                      {position.type === 'simulated' && (
                        <Chip
                          label="SIM"
                          color="warning"
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </Box>

                  {/* PnL Display */}
                  <Box textAlign="center" mb={2} p={1} bgcolor="background.default" borderRadius={1}>
                    <Typography 
                      variant="h5" 
                      color={position.unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
                      fontWeight="bold"
                    >
                      ${position.unrealized_pnl?.toFixed(2)}
                    </Typography>
                    <Typography 
                      variant="body2" 
                      color={position.unrealized_pnl_percent >= 0 ? 'success.main' : 'error.main'}
                    >
                      ({position.unrealized_pnl_percent >= 0 ? '+' : ''}{position.unrealized_pnl_percent?.toFixed(2)}%)
                    </Typography>
                  </Box>

                  <Divider sx={{ mb: 2 }} />

                  {/* Position Details */}
                  <Stack spacing={1}>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="textSecondary">Size:</Typography>
                      <Typography variant="body2">{position.size?.toFixed(6)}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="textSecondary">Entry:</Typography>
                      <Typography variant="body2">${position.entry_price?.toFixed(4)}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="textSecondary">Current:</Typography>
                      <Typography variant="body2">${position.current_price?.toFixed(4)}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="textSecondary">Leverage:</Typography>
                      <Typography variant="body2">{position.leverage?.toFixed(1)}x</Typography>
                    </Box>
                    {position.stop_loss && (
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="error.main">Stop Loss:</Typography>
                        <Typography variant="body2" color="error.main">${position.stop_loss?.toFixed(4)}</Typography>
                      </Box>
                    )}
                    {position.take_profit && (
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="success.main">Take Profit:</Typography>
                        <Typography variant="body2" color="success.main">${position.take_profit?.toFixed(4)}</Typography>
                      </Box>
                    )}
                    {position.strategy && (
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="textSecondary">Strategy:</Typography>
                        <Typography variant="body2">{position.strategy}</Typography>
                      </Box>
                    )}
                  </Stack>

                  {/* Status */}
                  <Box textAlign="center" mt={2}>
                    <Chip
                      label={position.status?.toUpperCase() || 'UNKNOWN'}
                      color={position.status === 'open' ? 'success' : 'default'}
                      size="small"
                    />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );
};

export default Positions; 