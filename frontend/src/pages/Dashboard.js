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
  Divider,
  LinearProgress
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningIcon from '@mui/icons-material/Warning';
import axios from 'axios';
import config from '../config';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');
  const [sortBy, setSortBy] = useState('pnl');
  const [sortOrder, setSortOrder] = useState('desc');
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error in dashboard:', error);
    let errorMessage = 'Failed to fetch dashboard data';

    if (error.response) {
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Dashboard endpoint not found. Please check the API configuration.';
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

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsResponse, positionsResponse] = await Promise.all([
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.STATS}`, {
          params: { timeRange },
          timeout: 5000
        }),
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.POSITIONS}`, {
          timeout: 5000
        })
      ]);

      setStats(statsResponse.data);
      setPositions(positionsResponse.data.positions || []);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchDashboardData, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, [retryCount, timeRange]);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const sortedPositions = [...positions].sort((a, b) => {
    const multiplier = sortOrder === 'asc' ? 1 : -1;
    switch (sortBy) {
      case 'pnl':
        return (a.pnl - b.pnl) * multiplier;
      case 'size':
        return (a.size - b.size) * multiplier;
      case 'leverage':
        return (a.leverage - b.leverage) * multiplier;
      default:
        return 0;
    }
  });

  const getTotalPnL = () => {
    return positions.reduce((sum, pos) => sum + pos.pnl, 0);
  };

  const getRiskLevel = () => {
    if (!stats) return 'low';
    const drawdown = stats.max_drawdown;
    if (drawdown > 0.15) return 'high';
    if (drawdown > 0.1) return 'medium';
    return 'low';
  };

  if (loading && !stats) {
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
          Trading Dashboard
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Chip
            label={`Total PnL: ${getTotalPnL().toFixed(2)}%`}
            color={getTotalPnL() >= 0 ? 'success' : 'error'}
            icon={getTotalPnL() >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />}
          />
          <Chip
            label={`Risk Level: ${getRiskLevel().toUpperCase()}`}
            color={getRiskLevel() === 'high' ? 'error' : getRiskLevel() === 'medium' ? 'warning' : 'success'}
            icon={getRiskLevel() === 'high' ? <WarningIcon /> : null}
          />
          <Tooltip title="Refresh dashboard">
            <IconButton onClick={fetchDashboardData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

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
              <Button color="inherit" size="small" onClick={fetchDashboardData}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Box mb={3}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Time Range</InputLabel>
              <Select
                value={timeRange}
                label="Time Range"
                onChange={(e) => setTimeRange(e.target.value)}
              >
                <MenuItem value="1h">Last Hour</MenuItem>
                <MenuItem value="24h">Last 24 Hours</MenuItem>
                <MenuItem value="7d">Last 7 Days</MenuItem>
                <MenuItem value="30d">Last 30 Days</MenuItem>
                <MenuItem value="all">All Time</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Sort Positions By</InputLabel>
              <Select
                value={sortBy}
                label="Sort Positions By"
                onChange={(e) => handleSort(e.target.value)}
              >
                <MenuItem value="pnl">PnL</MenuItem>
                <MenuItem value="size">Size</MenuItem>
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

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Total Trades
                </Typography>
                <Typography variant="h6">
                  {stats?.total_trades || 0}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Win Rate
                </Typography>
                <Typography variant="h6" color={stats?.win_rate >= 0.5 ? 'success.main' : 'error.main'}>
                  {(stats?.win_rate * 100 || 0).toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Profit Factor
                </Typography>
                <Typography variant="h6" color={stats?.profit_factor >= 1 ? 'success.main' : 'error.main'}>
                  {stats?.profit_factor?.toFixed(2) || 0}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Max Drawdown
                </Typography>
                <Typography variant="h6" color="error.main">
                  {(stats?.max_drawdown * 100 || 0).toFixed(1)}%
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Risk Metrics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Typography color="textSecondary" variant="body2">
                  Daily Risk Usage
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={(stats?.daily_risk_usage || 0) * 100} 
                  color={stats?.daily_risk_usage > 0.8 ? 'error' : stats?.daily_risk_usage > 0.5 ? 'warning' : 'success'}
                  sx={{ height: 10, borderRadius: 5, mb: 1 }}
                />
                <Typography variant="body2" color="textSecondary">
                  {(stats?.daily_risk_usage * 100 || 0).toFixed(1)}% of daily risk limit used
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Current Leverage
                </Typography>
                <Typography variant="h6" color={stats?.current_leverage > 3 ? 'error.main' : 'success.main'}>
                  {stats?.current_leverage?.toFixed(1) || 0}x
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography color="textSecondary" variant="body2">
                  Portfolio Beta
                </Typography>
                <Typography variant="h6" color={Math.abs(stats?.portfolio_beta || 0) > 1 ? 'warning.main' : 'success.main'}>
                  {(stats?.portfolio_beta || 0).toFixed(2)}
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Active Positions
            </Typography>
            {sortedPositions.length === 0 ? (
              <Typography color="textSecondary" align="center">
                No active positions
              </Typography>
            ) : (
              <Grid container spacing={2}>
                {sortedPositions.map((position) => (
                  <Grid item xs={12} sm={6} md={4} key={position.id}>
                    <Card>
                      <CardContent>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                          <Typography variant="h6">{position.symbol}</Typography>
                          <Chip
                            label={`${position.pnl.toFixed(2)}%`}
                            color={position.pnl >= 0 ? 'success' : 'error'}
                            size="small"
                          />
                        </Box>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Size
                            </Typography>
                            <Typography variant="body1">
                              {position.size.toFixed(4)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Leverage
                            </Typography>
                            <Typography variant="body1">
                              {position.leverage}x
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Entry Price
                            </Typography>
                            <Typography variant="body1">
                              {position.entry_price.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Current Price
                            </Typography>
                            <Typography variant="body1">
                              {position.current_price.toFixed(2)}
                            </Typography>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
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

export default Dashboard; 