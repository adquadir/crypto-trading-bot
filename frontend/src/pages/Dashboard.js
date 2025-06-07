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
  LinearProgress,
  Tabs,
  Tab
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningIcon from '@mui/icons-material/Warning';
import axios from 'axios';
import config from '../config';

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_trades: 0,
    win_rate: 0,
    profit_factor: 0,
    max_drawdown: 0,
    daily_risk_usage: 0,
    current_leverage: 0,
    portfolio_beta: 0,
    profile_performance: {},
    parameter_history: [],
    volatility_impact: {}
  });
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');
  const [sortBy, setSortBy] = useState('pnl');
  const [sortOrder, setSortOrder] = useState('desc');
  const [activeTab, setActiveTab] = useState(0);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error (raw):', error);
    let errorMessage = 'Failed to fetch dashboard data';

    // FIRST AND FOREMOST: Ensure 'error' is a non-null object.
    // If not, convert it to a string for display and stop processing.
    if (typeof error !== 'object' || error === null) {
      errorMessage = `An unexpected error occurred: ${String(error)}`;
      setError(errorMessage);
      return;
    }

    // Safely access error.response and its status
    if (error.response && typeof error.response === 'object' && typeof error.response.status !== 'undefined') {
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
      // error.request exists, which means a request was made but no response was received (e.g., network error, timeout)
      errorMessage = 'No response from server. Please check your connection.';
    } else if (typeof error.code !== 'undefined' && error.code === 'ECONNABORTED') {
      // Specific check for Axios timeout code
      errorMessage = 'Request timed out. Please try again.';
    } else {
      // Fallback for any other unexpected error formats (objects that lack specific properties, or custom errors)
      // Use error.message if available, otherwise try to stringify the object, or default to 'unknown'.
      errorMessage = `An unexpected error occurred: ${error.message || (error.toString ? error.toString() : JSON.stringify(error)) || 'unknown'}`;
    }

    setError(errorMessage);
  };

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsResponse, positionsResponse] = await Promise.all([
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.STATS}`, {
          timeout: 5000
        }),
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.POSITIONS}`, {
          timeout: 5000
        })
      ]);

      setStats(statsResponse.data.stats || stats);
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
    const interval = setInterval(fetchDashboardData, 30000);
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

  const getTotalPnL = () => {
    return positions.reduce((sum, pos) => sum + (pos.pnl || 0), 0);
  };

  const getRiskLevel = () => {
    if (!stats) return 'low';
    const drawdown = stats.max_drawdown || 0;
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
            label={`Total PnL: ${(getTotalPnL() || 0).toFixed(2)}%`}
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

      <Tabs
        value={activeTab}
        onChange={(_, newValue) => setActiveTab(newValue)}
        sx={{ mb: 3 }}
      >
        <Tab label="Overview" />
        <Tab label="Profile Performance" />
        <Tab label="Parameter History" />
      </Tabs>

      {activeTab === 0 && (
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
                    {stats.total_trades}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography color="textSecondary" variant="body2">
                    Win Rate
                  </Typography>
                  <Typography variant="h6" color={stats.win_rate >= 0.5 ? 'success.main' : 'error.main'}>
                    {(stats.win_rate * 100).toFixed(1)}%
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography color="textSecondary" variant="body2">
                    Profit Factor
                  </Typography>
                  <Typography variant="h6" color={stats.profit_factor >= 1 ? 'success.main' : 'error.main'}>
                    {stats.profit_factor.toFixed(2)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography color="textSecondary" variant="body2">
                    Max Drawdown
                  </Typography>
                  <Typography variant="h6" color={stats.max_drawdown > 0.15 ? 'error.main' : 'warning.main'}>
                    {(stats.max_drawdown * 100).toFixed(1)}%
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
                    value={(stats.daily_risk_usage || 0) * 100}
                    color={(stats.daily_risk_usage || 0) > 0.8 ? 'error' : (stats.daily_risk_usage || 0) > 0.5 ? 'warning' : 'success'}
                    sx={{ height: 10, borderRadius: 5, mb: 1 }}
                  />
                  <Typography variant="body2" color="textSecondary">
                    {((stats.daily_risk_usage || 0) * 100).toFixed(1)}% of daily risk limit used
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography color="textSecondary" variant="body2">
                    Current Leverage
                  </Typography>
                  <Typography variant="h6" color={(stats.current_leverage || 0) > 3 ? 'error.main' : 'success.main'}>
                    {(stats.current_leverage || 0).toFixed(1)}x
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography color="textSecondary" variant="body2">
                    Portfolio Beta
                  </Typography>
                  <Typography variant="h6" color={Math.abs(stats.portfolio_beta || 0) > 1 ? 'warning.main' : 'success.main'}>
                    {(stats.portfolio_beta || 0).toFixed(2)}
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
              <Grid container spacing={2}>
                {positions.map((position) => (
                  <Grid item xs={12} sm={6} md={4} key={position.symbol}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          {position.symbol}
                        </Typography>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Size
                            </Typography>
                            <Typography variant="body1">
                              {position.size}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              PnL
                            </Typography>
                            <Typography variant="body1" color={position.pnl >= 0 ? 'success.main' : 'error.main'}>
                              {position.pnl.toFixed(2)}%
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Entry Price
                            </Typography>
                            <Typography variant="body1">
                              ${position.entry_price.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Current Price
                            </Typography>
                            <Typography variant="body1">
                              ${position.current_price.toFixed(2)}
                            </Typography>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      )}

      {activeTab === 1 && (
        <Grid container spacing={3}>
          {Object.entries(stats.profile_performance || {}).map(([profile, performance]) => (
            <Grid item xs={12} md={4} key={profile}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  {profile.charAt(0).toUpperCase() + profile.slice(1)} Profile
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Win Rate
                    </Typography>
                    <Typography variant="h6" color={performance.win_rate >= 0.5 ? 'success.main' : 'error.main'}>
                      {(performance.win_rate * 100).toFixed(1)}%
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Profit Factor
                    </Typography>
                    <Typography variant="h6" color={performance.profit_factor >= 1 ? 'success.main' : 'error.main'}>
                      {performance.profit_factor.toFixed(2)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Total Trades
                    </Typography>
                    <Typography variant="h6">
                      {performance.total_trades}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Avg Trade Duration
                    </Typography>
                    <Typography variant="h6">
                      {performance.avg_duration}
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography color="textSecondary" variant="body2">
                      Parameter Adjustments
                    </Typography>
                    <Typography variant="body2">
                      {performance.parameter_adjustments} adjustments in last 24h
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Parameter Adaptation History
              </Typography>
              <Grid container spacing={2}>
                {stats.parameter_history?.map((entry, index) => (
                  <Grid item xs={12} key={index}>
                    <Card>
                      <CardContent>
                        <Typography variant="subtitle1" gutterBottom>
                          {new Date(entry.timestamp).toLocaleString()}
                        </Typography>
                        <Grid container spacing={2}>
                          <Grid item xs={12} md={6}>
                            <Typography color="textSecondary" variant="body2">
                              Profile
                            </Typography>
                            <Typography variant="body1">
                              {entry.profile}
                            </Typography>
                          </Grid>
                          <Grid item xs={12} md={6}>
                            <Typography color="textSecondary" variant="body2">
                              Trigger
                            </Typography>
                            <Typography variant="body1">
                              {entry.trigger}
                            </Typography>
                          </Grid>
                          <Grid item xs={12}>
                            <Typography color="textSecondary" variant="body2">
                              Changes
                            </Typography>
                            {Object.entries(entry.changes).map(([param, value]) => (
                              <Typography key={param} variant="body2">
                                {param}: {value}
                              </Typography>
                            ))}
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>

          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Volatility Impact
              </Typography>
              <Grid container spacing={2}>
                {Object.entries(stats.volatility_impact || {}).map(([profile, impact]) => (
                  <Grid item xs={12} md={4} key={profile}>
                    <Card>
                      <CardContent>
                        <Typography variant="subtitle1" gutterBottom>
                          {profile.charAt(0).toUpperCase() + profile.slice(1)} Profile
                        </Typography>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Current Volatility
                            </Typography>
                            <Typography variant="body1">
                              {impact.current_volatility.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Impact Factor
                            </Typography>
                            <Typography variant="body1">
                              {impact.impact_factor.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={12}>
                            <Typography color="textSecondary" variant="body2">
                              Parameter Adjustments
                            </Typography>
                            {Object.entries(impact.parameter_adjustments).map(([param, value]) => (
                              <Typography key={param} variant="body2">
                                {param}: {value}
                              </Typography>
                            ))}
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default Dashboard; 