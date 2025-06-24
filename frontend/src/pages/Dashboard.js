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
  Tab,
  Container,
  Stack,
  useMediaQuery,
  useTheme
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningIcon from '@mui/icons-material/Warning';
import axios from 'axios';
import config from '../config';

const Dashboard = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

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
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
          {!isMobile && (
            <Typography variant="h6" sx={{ ml: 2 }}>
              Loading Dashboard...
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
        <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold">
          Trading Dashboard
        </Typography>
        
        {/* Mobile-Optimized Action Chips */}
        <Stack 
          direction={{ xs: 'column', sm: 'row' }} 
          spacing={1}
          alignItems={{ xs: 'stretch', sm: 'center' }}
        >
          <Chip
            label={`Total PnL: ${(getTotalPnL() || 0).toFixed(2)}%`}
            color={getTotalPnL() >= 0 ? 'success' : 'error'}
            icon={getTotalPnL() >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />}
            size={isMobile ? "medium" : "small"}
            sx={{ 
              fontWeight: 'bold',
              minHeight: { xs: '32px', sm: 'auto' }
            }}
          />
          <Chip
            label={`Risk: ${getRiskLevel().toUpperCase()}`}
            color={getRiskLevel() === 'high' ? 'error' : getRiskLevel() === 'medium' ? 'warning' : 'success'}
            icon={getRiskLevel() === 'high' ? <WarningIcon /> : null}
            size={isMobile ? "medium" : "small"}
            sx={{ 
              fontWeight: 'bold',
              minHeight: { xs: '32px', sm: 'auto' }
            }}
          />
          <Tooltip title="Refresh dashboard">
            <IconButton 
              onClick={fetchDashboardData} 
              disabled={loading}
              sx={{ 
                alignSelf: { xs: 'center', sm: 'auto' },
                minWidth: { xs: '48px', sm: 'auto' }
              }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Stack>
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
            sx={{ width: '100%' }}
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      {/* Mobile-Optimized Tabs */}
      <Paper sx={{ mb: { xs: 2, sm: 3 } }}>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
          variant={isMobile ? "scrollable" : "standard"}
          scrollButtons={isMobile ? "auto" : false}
          allowScrollButtonsMobile
          sx={{
            '& .MuiTab-root': {
              fontSize: { xs: '0.75rem', sm: '0.875rem' },
              minWidth: { xs: '80px', sm: '120px' },
              padding: { xs: '8px 12px', sm: '12px 16px' }
            }
          }}
        >
          <Tab label="Overview" />
          <Tab label={isMobile ? "Profiles" : "Profile Performance"} />
          <Tab label={isMobile ? "History" : "Parameter History"} />
        </Tabs>
      </Paper>

      {activeTab === 0 && (
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          {/* Performance Metrics */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Performance Metrics
              </Typography>
              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid item xs={6} sm={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Total Trades
                    </Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold">
                      {stats.total_trades}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Win Rate
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={stats.win_rate >= 0.5 ? 'success.main' : 'error.main'}
                    >
                      {(stats.win_rate * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Profit Factor
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={stats.profit_factor >= 1 ? 'success.main' : 'error.main'}
                    >
                      {stats.profit_factor.toFixed(2)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Max Drawdown
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={stats.max_drawdown > 0.15 ? 'error.main' : 'warning.main'}
                    >
                      {(stats.max_drawdown * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          </Grid>

          {/* Risk Metrics */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Risk Metrics
              </Typography>
              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid item xs={12}>
                  <Typography color="textSecondary" variant="body2" gutterBottom>
                    Daily Risk Usage
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={(stats.daily_risk_usage || 0) * 100}
                    color={(stats.daily_risk_usage || 0) > 0.8 ? 'error' : (stats.daily_risk_usage || 0) > 0.5 ? 'warning' : 'success'}
                    sx={{ 
                      height: { xs: 8, sm: 10 }, 
                      borderRadius: 5, 
                      mb: 1 
                    }}
                  />
                  <Typography variant="body2" color="textSecondary">
                    {((stats.daily_risk_usage || 0) * 100).toFixed(1)}% of daily risk limit used
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Current Leverage
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={(stats.current_leverage || 0) > 3 ? 'error.main' : 'success.main'}
                    >
                      {(stats.current_leverage || 0).toFixed(1)}x
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography color="textSecondary" variant="body2" gutterBottom>
                      Portfolio Beta
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={Math.abs(stats.portfolio_beta || 0) > 1 ? 'warning.main' : 'success.main'}
                    >
                      {(stats.portfolio_beta || 0).toFixed(2)}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          </Grid>

          {/* Active Positions - Mobile Optimized */}
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Active Positions
              </Typography>
              <Grid container spacing={{ xs: 1, sm: 2, md: 3 }}>
                {positions.map((position) => (
                  <Grid item xs={12} sm={6} lg={4} key={position.symbol}>
                    <Card 
                      variant="outlined" 
                      sx={{ 
                        border: '1px solid',
                        borderColor: position.pnl >= 0 ? 'success.main' : 'error.main',
                        '&:hover': { boxShadow: 2 }
                      }}
                    >
                      <CardContent sx={{ p: { xs: 1.5, sm: 2 } }}>
                        <Typography variant="h6" gutterBottom fontWeight="bold">
                          {position.symbol}
                        </Typography>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="caption">
                              Size
                            </Typography>
                            <Typography variant="body2" fontWeight="medium">
                              {position.size}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="caption">
                              PnL
                            </Typography>
                            <Typography 
                              variant="body2" 
                              fontWeight="bold"
                              color={position.pnl >= 0 ? 'success.main' : 'error.main'}
                            >
                              {position.pnl.toFixed(2)}%
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="caption">
                              Entry
                            </Typography>
                            <Typography variant="body2" fontWeight="medium">
                              ${position.entry_price.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="caption">
                              Current
                            </Typography>
                            <Typography variant="body2" fontWeight="medium">
                              ${position.current_price.toFixed(2)}
                            </Typography>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
                {positions.length === 0 && (
                  <Grid item xs={12}>
                    <Box 
                      display="flex" 
                      justifyContent="center" 
                      alignItems="center" 
                      minHeight="100px"
                      color="text.secondary"
                    >
                      <Typography variant="body1">
                        No active positions
                      </Typography>
                    </Box>
                  </Grid>
                )}
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      )}

      {activeTab === 1 && (
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          {Object.entries(stats.profile_performance || {}).map(([profile, performance]) => (
            <Grid item xs={12} sm={6} lg={4} key={profile}>
              <Paper sx={{ p: { xs: 2, sm: 3 } }}>
                <Typography variant="h6" gutterBottom>
                  {profile.charAt(0).toUpperCase() + profile.slice(1)} Profile
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Win Rate
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={performance.win_rate >= 0.5 ? 'success.main' : 'error.main'}
                    >
                      {(performance.win_rate * 100).toFixed(1)}%
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Profit Factor
                    </Typography>
                    <Typography 
                      variant={isMobile ? "h5" : "h4"} 
                      fontWeight="bold"
                      color={performance.profit_factor >= 1 ? 'success.main' : 'error.main'}
                    >
                      {performance.profit_factor.toFixed(2)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Total Trades
                    </Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold">
                      {performance.total_trades}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography color="textSecondary" variant="body2">
                      Avg Duration
                    </Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold">
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
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Parameter Adaptation History
              </Typography>
              <Stack spacing={2}>
                {stats.parameter_history?.map((entry, index) => (
                  <Card key={index} variant="outlined">
                    <CardContent sx={{ p: { xs: 1.5, sm: 2 } }}>
                      <Typography variant="subtitle1" gutterBottom fontWeight="medium">
                        {new Date(entry.timestamp).toLocaleString()}
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={12} sm={6}>
                          <Typography color="textSecondary" variant="body2">
                            Profile
                          </Typography>
                          <Typography variant="body1" fontWeight="medium">
                            {entry.profile}
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography color="textSecondary" variant="body2">
                            Trigger
                          </Typography>
                          <Typography variant="body1" fontWeight="medium">
                            {entry.trigger}
                          </Typography>
                        </Grid>
                        <Grid item xs={12}>
                          <Typography color="textSecondary" variant="body2" gutterBottom>
                            Changes
                          </Typography>
                          <Stack spacing={0.5}>
                            {Object.entries(entry.changes).map(([param, value]) => (
                              <Typography key={param} variant="body2">
                                <strong>{param}:</strong> {value}
                              </Typography>
                            ))}
                          </Stack>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                )) || (
                  <Typography color="text.secondary" textAlign="center" py={4}>
                    No parameter history available
                  </Typography>
                )}
              </Stack>
            </Paper>
          </Grid>

          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Volatility Impact
              </Typography>
              <Grid container spacing={2}>
                {Object.entries(stats.volatility_impact || {}).map(([profile, impact]) => (
                  <Grid item xs={12} sm={6} lg={4} key={profile}>
                    <Card variant="outlined">
                      <CardContent sx={{ p: { xs: 1.5, sm: 2 } }}>
                        <Typography variant="subtitle1" gutterBottom fontWeight="medium">
                          {profile.charAt(0).toUpperCase() + profile.slice(1)} Profile
                        </Typography>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Current Volatility
                            </Typography>
                            <Typography variant="body1" fontWeight="medium">
                              {impact.current_volatility.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography color="textSecondary" variant="body2">
                              Impact Factor
                            </Typography>
                            <Typography variant="body1" fontWeight="medium">
                              {impact.impact_factor.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={12}>
                            <Typography color="textSecondary" variant="body2" gutterBottom>
                              Parameter Adjustments
                            </Typography>
                            <Stack spacing={0.5}>
                              {Object.entries(impact.parameter_adjustments || {}).map(([param, value]) => (
                                <Typography key={param} variant="body2">
                                  <strong>{param}:</strong> {value}
                                </Typography>
                              ))}
                            </Stack>
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

      {/* Last Updated Indicator */}
      {lastUpdated && !isMobile && (
        <Box textAlign="center" mt={2}>
          <Typography variant="caption" color="text.secondary">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default Dashboard; 