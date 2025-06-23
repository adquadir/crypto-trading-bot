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
  Button,
  Chip,
  Stack,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tab,
  Tabs
} from '@mui/material';
import {
  Assessment as AssessmentIcon,
  TrendingUp as TrendingUpIcon,
  Star as StarIcon,
  Speed as SpeedIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import axios from 'axios';
import config from '../config';

const Performance = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [performanceData, setPerformanceData] = useState(null);
  const [goldenSignals, setGoldenSignals] = useState([]);
  const [liveTracking, setLiveTracking] = useState(null);
  const [adaptiveAssessment, setAdaptiveAssessment] = useState(null);
  const [realTimeActive, setRealTimeActive] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    // Initial data fetch for all tabs
    fetchAllData();
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    // Setup real-time polling for live tracking tab
    if (activeTab === 2) { // Live Tracking tab
      startRealTimePolling();
    } else {
      stopRealTimePolling();
    }
    
    return () => stopRealTimePolling();
  }, [activeTab]);

  const startRealTimePolling = () => {
    if (intervalRef.current) return; // Already running
    
    setRealTimeActive(true);
    console.log('🔴 Starting real-time polling every 3 seconds...');
    
    // Immediate fetch
    fetchLiveTrackingData();
    
    // Then poll every 3 seconds
    intervalRef.current = setInterval(() => {
      fetchLiveTrackingData();
    }, 3000);
  };

  const stopRealTimePolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
      setRealTimeActive(false);
      console.log('⏹️ Stopped real-time polling');
    }
  };

  const fetchLiveTrackingData = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}/api/v1/signals/live-tracking`);
      if (response.data.status === 'success') {
        setLiveTracking(response.data.data || {});
        console.log('📊 Live tracking updated:', {
          activeSignals: response.data.data?.active_signals_count || 0,
          monitoredSymbols: response.data.data?.price_cache_symbols || 0
        });
      }
    } catch (err) {
      console.error('Error fetching live tracking:', err);
      // Don't show error for polling failures
    }
  };

  const fetchAllData = async () => {
    try {
      setLoading(true);
      
      const [performanceRes, goldenRes, liveRes, adaptiveRes] = await Promise.all([
        axios.get(`${config.API_BASE_URL}/api/v1/signals/performance`),
        axios.get(`${config.API_BASE_URL}/api/v1/signals/golden`),
        axios.get(`${config.API_BASE_URL}/api/v1/signals/live-tracking`),
        axios.get(`${config.API_BASE_URL}/api/v1/signals/adaptive-assessment`)
      ]);

      // Handle performance data - check if it has performance_metrics or different structure
      if (performanceRes.data.success || performanceRes.data.status === 'success') {
        const perfData = performanceRes.data.data;
        if (perfData && perfData.performance_metrics) {
          // Transform the actual API response to expected format
          const transformedData = {
            overall: {
              total_signals: perfData.performance_metrics.total_signals,
              signals_3pct: Math.round(perfData.performance_metrics.total_signals * perfData.performance_metrics.win_rate),
              golden_signals: perfData.performance_metrics.winning_signals || 0,
              avg_time_to_3pct: perfData.performance_metrics.avg_duration_minutes || 0
            },
            by_strategy: [] // Will be populated if available
          };
          setPerformanceData(transformedData);
        } else if (perfData) {
          setPerformanceData(perfData);
        }
      }
      
      if (goldenRes.data.status === 'success') {
        setGoldenSignals(goldenRes.data.data || []);
      }
      
      if (liveRes.data.status === 'success') {
        setLiveTracking(liveRes.data.data || {});
      }
      
      if (adaptiveRes.data.status === 'success') {
        setAdaptiveAssessment(adaptiveRes.data);
      }
      
      setError(null);
    } catch (err) {
      setError('Failed to fetch performance data');
      console.error('Error fetching performance data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const getPerformanceGrade = (hitRate) => {
    if (hitRate >= 60) return { grade: 'A', color: 'success' };
    if (hitRate >= 40) return { grade: 'B', color: 'warning' };
    if (hitRate >= 25) return { grade: 'C', color: 'info' };
    return { grade: 'D', color: 'error' };
  };

  if (loading && !performanceData) {
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
          <Typography variant="h4" color="primary">
            Performance Analytics
          </Typography>
          <Typography variant="body1" color="textSecondary">
            Real-time signal tracking and adaptive learning insights
            {realTimeActive && (
              <Chip 
                label="🔴 LIVE (3s)" 
                color="success" 
                size="small" 
                sx={{ ml: 2 }}
              />
            )}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={fetchAllData}
          disabled={loading}
        >
          Refresh All Data
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Performance Overview" />
          <Tab label="Golden Signals" />
          <Tab label="Live Tracking" />
          <Tab label="Adaptive Assessment" />
        </Tabs>
      </Paper>

      {/* Performance Overview Tab */}
      {activeTab === 0 && performanceData && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Overall Performance (Last 7 Days)
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} sm={6} md={3}>
                  <Card>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="primary">
                        {performanceData.overall?.total_signals || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Total Signals Tracked
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="success.main">
                        {((performanceData.overall?.signals_3pct || 0) / Math.max(performanceData.overall?.total_signals || 1, 1) * 100).toFixed(1)}%
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        3% Hit Rate
                      </Typography>
                      <Chip 
                        label={getPerformanceGrade((performanceData.overall?.signals_3pct || 0) / Math.max(performanceData.overall?.total_signals || 1, 1) * 100).grade}
                        color={getPerformanceGrade((performanceData.overall?.signals_3pct || 0) / Math.max(performanceData.overall?.total_signals || 1, 1) * 100).color}
                        size="small"
                        sx={{ mt: 1 }}
                      />
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="warning.main">
                        {performanceData.overall?.golden_signals || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Golden Signals
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="info.main">
                        {(performanceData.overall?.avg_time_to_3pct || 0).toFixed(1)}m
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Avg Time to 3%
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Paper>
          </Grid>

          {/* Strategy Performance */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Strategy Performance Rankings
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Strategy</TableCell>
                      <TableCell align="right">Total</TableCell>
                      <TableCell align="right">3% Hit Rate</TableCell>
                      <TableCell align="right">Golden Signals</TableCell>
                      <TableCell align="right">Performance</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(performanceData.by_strategy || []).map((strategy) => {
                      const hitRate = (strategy.hit_3pct / Math.max(strategy.total, 1)) * 100;
                      const grade = getPerformanceGrade(hitRate);
                      
                      return (
                        <TableRow key={strategy.strategy}>
                          <TableCell>{strategy.strategy}</TableCell>
                          <TableCell align="right">{strategy.total}</TableCell>
                          <TableCell align="right">{hitRate.toFixed(1)}%</TableCell>
                          <TableCell align="right">{strategy.golden}</TableCell>
                          <TableCell align="right">
                            <Chip 
                              label={grade.grade}
                              color={grade.color}
                              size="small"
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Golden Signals Tab */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Golden Signals (Quick 3% Gainers)
              </Typography>
              {goldenSignals.length === 0 ? (
                <Alert severity="info">
                  No golden signals yet. Golden signals are those that hit 3% profit within 60 minutes.
                </Alert>
              ) : (
                <Grid container spacing={2}>
                  {goldenSignals.map((signal, index) => (
                    <Grid item xs={12} sm={6} md={4} key={index}>
                      <Card sx={{ border: '2px solid', borderColor: 'warning.main' }}>
                        <CardContent>
                          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                            <Typography variant="h6">{signal.symbol}</Typography>
                            <Chip 
                              icon={<StarIcon />}
                              label="GOLDEN" 
                              color="warning" 
                              size="small"
                            />
                          </Box>
                          <Stack spacing={1}>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="textSecondary">Strategy:</Typography>
                              <Typography variant="body2">{signal.strategy}</Typography>
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="textSecondary">Direction:</Typography>
                              <Chip 
                                label={signal.direction}
                                color={signal.direction === 'LONG' ? 'success' : 'error'}
                                size="small"
                              />
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="textSecondary">Time to 3%:</Typography>
                              <Typography variant="body2" fontWeight="bold" color="success.main">
                                {signal.time_to_3pct_minutes}m
                              </Typography>
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="textSecondary">Max PnL:</Typography>
                              <Typography variant="body2" fontWeight="bold" color="success.main">
                                {(signal.max_pnl_pct * 100).toFixed(2)}%
                              </Typography>
                            </Box>
                          </Stack>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Live Tracking Tab */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">
                  Live Signal Tracking
                </Typography>
                <Box display="flex" alignItems="center" gap={1}>
                  {realTimeActive ? (
                    <Chip 
                      label="🟢 Real-time Connected" 
                      color="success" 
                      size="small"
                    />
                  ) : (
                    <Chip 
                      label="🔴 Offline" 
                      color="error" 
                      size="small"
                    />
                  )}
                </Box>
              </Box>
              <Grid container spacing={2} mb={3}>
                <Grid item xs={12} sm={4}>
                  <Card sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'success.main' : 'divider',
                    transition: 'all 0.3s ease'
                  }}>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="primary" sx={{
                        transition: 'color 0.3s ease',
                        color: realTimeActive ? 'success.main' : 'primary.main'
                      }}>
                        {liveTracking?.active_signals_count || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Active Signals
                        {realTimeActive && <Typography variant="caption" display="block" color="success.main">● Live</Typography>}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Card sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'info.main' : 'divider',
                    transition: 'all 0.3s ease'
                  }}>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="info.main" sx={{
                        transition: 'color 0.3s ease'
                      }}>
                        {liveTracking?.price_cache_symbols || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Monitored Symbols
                        {realTimeActive && <Typography variant="caption" display="block" color="info.main">● Live</Typography>}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Card sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'success.main' : 'divider',
                    transition: 'all 0.3s ease'
                  }}>
                    <CardContent sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color={realTimeActive ? "success.main" : "grey.500"} sx={{
                        transition: 'color 0.3s ease'
                      }}>
                        {realTimeActive ? "LIVE" : "OFFLINE"}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Real-time Monitoring
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              {/* Active Signals */}
              {liveTracking?.active_signals?.length > 0 && (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Strategy</TableCell>
                        <TableCell>Direction</TableCell>
                        <TableCell align="right">Age</TableCell>
                        <TableCell align="right">Current PnL</TableCell>
                        <TableCell align="right">Max PnL</TableCell>
                        <TableCell>Targets Hit</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(liveTracking?.active_signals || []).map((signal, index) => (
                        <TableRow key={index}>
                          <TableCell>{signal.symbol}</TableCell>
                          <TableCell>{signal.strategy}</TableCell>
                          <TableCell>
                            <Chip 
                              label={signal.direction}
                              color={signal.direction === 'LONG' ? 'success' : 'error'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="right">{signal.age_minutes}m</TableCell>
                          <TableCell align="right">
                            <Typography 
                              color={signal.current_pnl_pct >= 0 ? 'success.main' : 'error.main'}
                              fontWeight="bold"
                              sx={{
                                transition: 'all 0.3s ease',
                                animation: realTimeActive ? 'pulse 2s infinite' : 'none',
                                '@keyframes pulse': {
                                  '0%': { opacity: 1 },
                                  '50%': { opacity: 0.7 },
                                  '100%': { opacity: 1 }
                                }
                              }}
                            >
                              {signal.current_pnl_pct >= 0 ? '+' : ''}{signal.current_pnl_pct}%
                              {realTimeActive && (
                                <Typography 
                                  component="span" 
                                  variant="caption" 
                                  sx={{ ml: 0.5, color: 'success.main' }}
                                >
                                  ●
                                </Typography>
                              )}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography 
                              color="success.main" 
                              fontWeight="bold"
                              sx={{
                                transition: 'all 0.3s ease'
                              }}
                            >
                              +{signal.max_profit_pct}%
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5}>
                              {signal.targets_hit?.['3pct'] && (
                                <Chip label="3%" color="success" size="small" />
                              )}
                              {signal.targets_hit?.['5pct'] && (
                                <Chip label="5%" color="success" size="small" />
                              )}
                              {signal.targets_hit?.stop_loss && (
                                <Chip label="SL" color="error" size="small" />
                              )}
                            </Stack>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Adaptive Assessment Tab */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Adaptive Market Assessment
              </Typography>
              
              {adaptiveAssessment?.market_regime && (
                <Grid container spacing={3} mb={3}>
                  <Grid item xs={12} md={6}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6" color="primary" gutterBottom>
                          Current Market Regime
                        </Typography>
                        <Chip 
                          label={adaptiveAssessment?.market_regime?.market_type || 'Unknown'}
                          color="primary"
                          sx={{ mb: 2, fontWeight: 'bold' }}
                        />
                        <Typography variant="body2" color="textSecondary">
                          {adaptiveAssessment?.market_regime?.characteristics || 'No data'}
                        </Typography>
                        <Divider sx={{ my: 2 }} />
                        <Stack spacing={1}>
                          <Box display="flex" justifyContent="space-between">
                            <Typography variant="body2">Volatility:</Typography>
                            <Typography variant="body2" fontWeight="bold">
                              {adaptiveAssessment?.market_regime?.avg_volatility || 0}%
                            </Typography>
                          </Box>
                          <Box display="flex" justifyContent="space-between">
                            <Typography variant="body2">Volume Ratio:</Typography>
                            <Typography variant="body2" fontWeight="bold">
                              {adaptiveAssessment?.market_regime?.avg_volume_ratio || 0}x
                            </Typography>
                          </Box>
                          <Box display="flex" justifyContent="space-between">
                            <Typography variant="body2">Learning Potential:</Typography>
                            <Chip 
                              label={adaptiveAssessment?.market_regime?.learning_potential || 'Unknown'}
                              color="success"
                              size="small"
                            />
                          </Box>
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>
                  
                  <Grid item xs={12} md={6}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6" color="primary" gutterBottom>
                          Adaptive Strategy
                        </Typography>
                        <Box display="flex" alignItems="center" gap={1} mb={2}>
                          <Typography variant="h4">{adaptiveAssessment?.adaptive_strategy?.emoji || '🔄'}</Typography>
                          <Typography variant="h6">{adaptiveAssessment?.adaptive_strategy?.action || 'Analyzing'}</Typography>
                        </Box>
                        <Typography variant="body2" color="textSecondary" mb={2}>
                          {adaptiveAssessment?.adaptive_strategy?.reasoning || 'Loading adaptive assessment...'}
                        </Typography>
                        <Divider sx={{ my: 2 }} />
                        <Box display="flex" justifyContent="space-between">
                          <Typography variant="body2">Risk per Trade:</Typography>
                          <Typography variant="body2" fontWeight="bold">
                            {adaptiveAssessment?.adaptive_strategy?.risk_per_trade || 'N/A'}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>
              )}

              {/* Show message when no adaptive data */}
              {!adaptiveAssessment?.market_regime && (
                <Alert severity="info">
                  Loading adaptive assessment data...
                </Alert>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default Performance; 