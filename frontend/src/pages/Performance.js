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
  Tabs,
  Container,
  useMediaQuery,
  useTheme
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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

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
      <Container maxWidth="xl">
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress size={isMobile ? 40 : 60} />
          {!isMobile && (
            <Typography variant="h6" sx={{ ml: 2 }}>
              Loading performance data...
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
          <Typography variant={isMobile ? "h5" : "h4"} color="primary" fontWeight="bold">
            Performance Analytics
          </Typography>
          <Typography 
            variant="body1" 
            color="text.secondary"
            sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}
          >
            Real-time signal tracking and adaptive learning insights
            {realTimeActive && !isMobile && (
              <Chip 
                label="🔴 LIVE (3s)" 
                color="success" 
                size="small" 
                sx={{ ml: 2 }}
              />
            )}
          </Typography>
        </Box>
        
        <Stack 
          direction={{ xs: 'column', sm: 'row' }} 
          spacing={1}
          alignItems={{ xs: 'stretch', sm: 'center' }}
        >
          {realTimeActive && isMobile && (
            <Chip 
              label="🔴 LIVE (3s)" 
              color="success" 
              size="medium" 
              sx={{ alignSelf: 'center' }}
            />
          )}
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={fetchAllData}
          disabled={loading}
            size={isMobile ? "medium" : "small"}
            sx={{ 
              minHeight: { xs: '44px', sm: 'auto' },
              fontSize: { xs: '0.875rem', sm: '0.75rem' }
            }}
        >
          Refresh All Data
        </Button>
        </Stack>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: { xs: 2, sm: 3 } }}>
          {error}
        </Alert>
      )}

      {/* Mobile-Optimized Tabs */}
      <Paper sx={{ mb: { xs: 2, sm: 3 } }}>
        <Tabs 
          value={activeTab} 
          onChange={handleTabChange}
          variant={isMobile ? "scrollable" : "standard"}
          scrollButtons={isMobile ? "auto" : false}
          allowScrollButtonsMobile
          sx={{
            '& .MuiTab-root': {
              fontSize: { xs: '0.75rem', sm: '0.875rem' },
              minWidth: { xs: '90px', sm: '140px' },
              padding: { xs: '8px 12px', sm: '12px 16px' }
            }
          }}
        >
          <Tab label={isMobile ? "Overview" : "Performance Overview"} />
          <Tab label={isMobile ? "Golden" : "Golden Signals"} />
          <Tab label={isMobile ? "Live" : "Live Tracking"} />
          <Tab label={isMobile ? "Adaptive" : "Adaptive Assessment"} />
        </Tabs>
      </Paper>

      {/* Performance Overview Tab */}
      {activeTab === 0 && performanceData && (
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Overall Performance (Last 7 Days)
              </Typography>
              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid item xs={6} sm={3}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography variant={isMobile ? "h5" : "h4"} color="primary" fontWeight="bold">
                        {performanceData.overall?.total_signals || 0}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Signals Tracked
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                        {((performanceData.overall?.signals_3pct || 0) / Math.max(performanceData.overall?.total_signals || 1, 1) * 100).toFixed(1)}%
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
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
                <Grid item xs={6} sm={3}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography variant={isMobile ? "h5" : "h4"} color="warning.main" fontWeight="bold">
                        {performanceData.overall?.golden_signals || 0}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Golden Signals
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography variant={isMobile ? "h5" : "h4"} color="info.main" fontWeight="bold">
                        {(performanceData.overall?.avg_time_to_3pct || 0).toFixed(1)}m
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Avg Time to 3%
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Paper>
          </Grid>

          {/* Strategy Performance - Mobile Optimized */}
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Strategy Performance Rankings
              </Typography>
              <TableContainer sx={{ 
                maxHeight: { xs: '400px', sm: 'none' },
                '&::-webkit-scrollbar': {
                  width: '6px',
                  height: '6px',
                },
                '&::-webkit-scrollbar-track': {
                  backgroundColor: 'rgba(255,255,255,0.1)',
                },
                '&::-webkit-scrollbar-thumb': {
                  backgroundColor: 'rgba(255,255,255,0.3)',
                  borderRadius: '3px',
                },
              }}>
                <Table size={isMobile ? "small" : "medium"}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'bold' }}>Strategy</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>Total</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>3% Hit Rate</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>Golden</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>Grade</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(performanceData.by_strategy || []).map((strategy) => {
                      const hitRate = (strategy.hit_3pct / Math.max(strategy.total, 1)) * 100;
                      const grade = getPerformanceGrade(hitRate);
                      
                      return (
                        <TableRow key={strategy.strategy} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {strategy.strategy}
                            </Typography>
                          </TableCell>
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
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Golden Signals (Quick 3% Gainers)
              </Typography>
              {goldenSignals.length === 0 ? (
                <Alert severity="info">
                  No golden signals yet. Golden signals are those that hit 3% profit within 60 minutes.
                </Alert>
              ) : (
                <Grid container spacing={{ xs: 1.5, sm: 2 }}>
                  {goldenSignals.map((signal, index) => (
                    <Grid item xs={12} sm={6} lg={4} key={index}>
                      <Card 
                        sx={{ 
                          border: '2px solid', 
                          borderColor: 'warning.main',
                          '&:hover': { boxShadow: 4 }
                        }}
                      >
                        <CardContent sx={{ p: { xs: 1.5, sm: 2 } }}>
                          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                            <Typography variant="h6" fontWeight="bold">{signal.symbol}</Typography>
                            <Chip 
                              icon={<StarIcon />}
                              label="GOLDEN" 
                              color="warning" 
                              size="small"
                            />
                          </Box>
                          <Stack spacing={1}>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="text.secondary">Strategy:</Typography>
                              <Typography variant="body2" fontWeight="medium">{signal.strategy}</Typography>
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="text.secondary">Direction:</Typography>
                              <Chip 
                                label={signal.direction}
                                color={signal.direction === 'LONG' ? 'success' : 'error'}
                                size="small"
                              />
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="text.secondary">Time to 3%:</Typography>
                              <Typography variant="body2" fontWeight="bold" color="success.main">
                                {signal.time_to_3pct_minutes}m
                              </Typography>
                            </Box>
                            <Box display="flex" justifyContent="space-between">
                              <Typography variant="body2" color="text.secondary">Max PnL:</Typography>
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
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Box 
                display="flex" 
                flexDirection={{ xs: 'column', sm: 'row' }}
                justifyContent="space-between" 
                alignItems={{ xs: 'stretch', sm: 'center' }} 
                mb={2}
                gap={{ xs: 1, sm: 0 }}
              >
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
              
              <Grid container spacing={{ xs: 1.5, sm: 2 }} mb={3}>
                <Grid item xs={12} sm={4}>
                  <Card 
                    variant="outlined"
                    sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'success.main' : 'divider',
                    transition: 'all 0.3s ease'
                    }}
                  >
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography 
                        variant={isMobile ? "h5" : "h4"} 
                        fontWeight="bold"
                        sx={{
                        transition: 'color 0.3s ease',
                        color: realTimeActive ? 'success.main' : 'primary.main'
                        }}
                      >
                        {liveTracking?.active_signals_count || 0}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Active Signals
                        {realTimeActive && (
                          <Typography variant="caption" display="block" color="success.main">
                            ● Live
                          </Typography>
                        )}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Card 
                    variant="outlined"
                    sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'info.main' : 'divider',
                    transition: 'all 0.3s ease'
                    }}
                  >
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography 
                        variant={isMobile ? "h5" : "h4"} 
                        color="info.main"
                        fontWeight="bold"
                        sx={{ transition: 'color 0.3s ease' }}
                      >
                        {liveTracking?.price_cache_symbols || 0}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Monitored Symbols
                        {realTimeActive && (
                          <Typography variant="caption" display="block" color="info.main">
                            ● Live
                          </Typography>
                        )}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Card 
                    variant="outlined"
                    sx={{ 
                    border: realTimeActive ? '2px solid' : '1px solid', 
                    borderColor: realTimeActive ? 'success.main' : 'divider',
                    transition: 'all 0.3s ease'
                    }}
                  >
                    <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
                      <Typography 
                        variant={isMobile ? "h5" : "h4"} 
                        fontWeight="bold"
                        color={realTimeActive ? "success.main" : "grey.500"}
                        sx={{ transition: 'color 0.3s ease' }}
                      >
                        {realTimeActive ? "LIVE" : "OFFLINE"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Real-time Monitoring
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              {/* Active Signals Table - Mobile Optimized */}
              {liveTracking?.active_signals?.length > 0 && (
                <TableContainer sx={{ 
                  maxHeight: { xs: '400px', sm: 'none' },
                  '&::-webkit-scrollbar': {
                    width: '6px',
                    height: '6px',
                  },
                  '&::-webkit-scrollbar-track': {
                    backgroundColor: 'rgba(255,255,255,0.1)',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    backgroundColor: 'rgba(255,255,255,0.3)',
                    borderRadius: '3px',
                  },
                }}>
                  <Table size={isMobile ? "small" : "medium"}>
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                        <TableCell sx={{ fontWeight: 'bold' }}>Strategy</TableCell>
                        <TableCell sx={{ fontWeight: 'bold' }}>Direction</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Age</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Current PnL</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Max PnL</TableCell>
                        <TableCell sx={{ fontWeight: 'bold' }}>Targets Hit</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {liveTracking.active_signals.map((signal, index) => (
                        <TableRow key={index} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {signal.symbol}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {signal.strategy}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={signal.direction}
                              color={signal.direction === 'LONG' ? 'success' : 'error'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2">
                              {signal.age_minutes}m
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography 
                              variant="body2" 
                              fontWeight="bold"
                              color={signal.current_pnl_pct >= 0 ? 'success.main' : 'error.main'}
                            >
                              {(signal.current_pnl_pct * 100).toFixed(2)}%
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" color="info.main">
                              {(signal.max_pnl_pct * 100).toFixed(2)}%
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5}>
                              {signal.targets_hit.map((target, i) => (
                                <Chip
                                  key={i}
                                  label={target}
                                  color="success"
                                  size="small"
                                  variant="outlined"
                                />
                              ))}
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
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: { xs: 2, sm: 3 } }}>
              <Typography variant="h6" gutterBottom>
                Adaptive Assessment
              </Typography>
              {adaptiveAssessment ? (
                <Box>
                  <Typography variant="body1" color="text.secondary">
                    Adaptive assessment data will be displayed here when available.
                            </Typography>
                          </Box>
              ) : (
                <Alert severity="info">
                  Adaptive assessment data is not currently available.
                </Alert>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}
    </Container>
  );
};

export default Performance; 