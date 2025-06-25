import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Alert,
  Stack,
  Divider,
  Switch,
  FormControlLabel,
  useMediaQuery,
  useTheme,
  CircularProgress
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  School as LearningIcon,
  Analytics as AnalyticsIcon,
  SmartToy as AIIcon,
  Timeline as TimelineIcon,
  AccountBalance as BalanceIcon,
  Speed as SpeedIcon
} from '@mui/icons-material';
import axios from 'axios';
import config from '../config';

const PaperTrading = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const [status, setStatus] = useState(null);
  const [positions, setPositions] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [learningInsights, setLearningInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statusResponse, positionsResponse, performanceResponse, insightsResponse] = await Promise.all([
        axios.get(`${config.API_BASE_URL}/api/v1/trading/paper-trading/status`),
        axios.get(`${config.API_BASE_URL}/api/v1/trading/paper-trading/positions`),
        axios.get(`${config.API_BASE_URL}/api/v1/trading/paper-trading/performance`),
        axios.get(`${config.API_BASE_URL}/api/v1/trading/paper-trading/learning-insights`)
      ]);

      setStatus(statusResponse.data.data);
      setPositions(positionsResponse.data.data);
      setPerformance(performanceResponse.data.data);
      setLearningInsights(insightsResponse.data.data);
      setIsRunning(statusResponse.data.data.enabled);
      setError(null);
    } catch (error) {
      console.error('Error fetching paper trading data:', error);
      setError('Failed to fetch paper trading data');
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    try {
      await axios.post(`${config.API_BASE_URL}/api/v1/trading/paper-trading/start`);
      setIsRunning(true);
      await fetchData();
    } catch (error) {
      console.error('Error starting paper trading:', error);
      setError('Failed to start paper trading');
    }
  };

  const handleStop = async () => {
    try {
      await axios.post(`${config.API_BASE_URL}/api/v1/trading/paper-trading/stop`);
      setIsRunning(false);
      await fetchData();
    } catch (error) {
      console.error('Error stopping paper trading:', error);
      setError('Failed to stop paper trading');
    }
  };

  const getReturnColor = (returnPct) => {
    if (returnPct > 0) return 'success.main';
    if (returnPct < 0) return 'error.main';
    return 'text.primary';
  };

  const getPnLColor = (pnl) => {
    if (pnl > 0) return 'success.main';
    if (pnl < 0) return 'error.main';
    return 'text.primary';
  };

  if (loading && !status) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={{ xs: 1, sm: 2, md: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight="bold" display="flex" alignItems="center" gap={1}>
            <AIIcon color="primary" />
            Live Paper Trading - ML Learning
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real market conditions • Zero risk • AI learning enabled
          </Typography>
        </Box>
        <Box display="flex" gap={1} alignItems="center">
          <Chip
            label={isRunning ? "LIVE LEARNING" : "STOPPED"}
            color={isRunning ? "success" : "default"}
            icon={isRunning ? <LearningIcon /> : <StopIcon />}
            sx={{ fontWeight: 'bold' }}
          />
          <Button
            variant="contained"
            color={isRunning ? "error" : "success"}
            onClick={isRunning ? handleStop : handleStart}
            startIcon={isRunning ? <StopIcon /> : <StartIcon />}
            disabled={loading}
          >
            {isRunning ? "Stop" : "Start"} Learning
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Status Overview */}
      {status && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <BalanceIcon color="primary" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="primary">
                  ${status.virtual_balance?.toLocaleString() || '0'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Virtual Balance
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <TrendingUpIcon sx={{ mb: 1, color: getReturnColor(status.total_return_pct) }} />
                <Typography 
                  variant="h5" 
                  fontWeight="bold"
                  color={getReturnColor(status.total_return_pct)}
                >
                  {status.total_return_pct?.toFixed(1) || '0'}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Total Return
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <SpeedIcon color="success" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="success.main">
                  {status.win_rate_pct?.toFixed(1) || '0'}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Win Rate
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center', p: 2 }}>
                <AnalyticsIcon color="info" sx={{ mb: 1 }} />
                <Typography variant="h5" fontWeight="bold" color="info.main">
                  {status.completed_trades || 0}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ML Training Trades
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Learning Insights Alert */}
      {status?.learning_insights && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            🧠 Real-Time ML Learning Insights
          </Typography>
          {status.learning_insights.map((insight, index) => (
            <Typography key={index} variant="body2" sx={{ mb: 0.5 }}>
              • {insight}
            </Typography>
          ))}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Strategy Performance */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                🎯 Strategy Performance Learning
              </Typography>
              {status?.strategy_performance && Object.entries(status.strategy_performance).map(([strategy, data]) => (
                <Box key={strategy} sx={{ mb: 2 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" fontWeight="bold" textTransform="capitalize">
                      {strategy.replace('_', ' ')}
                    </Typography>
                    <Chip 
                      label={`${(data.win_rate * 100).toFixed(1)}%`}
                      color={data.win_rate > 0.6 ? 'success' : data.win_rate > 0.5 ? 'warning' : 'error'}
                      size="small"
                    />
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={data.win_rate * 100}
                    color={data.win_rate > 0.6 ? 'success' : data.win_rate > 0.5 ? 'warning' : 'error'}
                    sx={{ height: 8, borderRadius: 1, mb: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {data.total_trades} trades • Avg PnL: ${data.avg_pnl?.toFixed(2)}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Grid>

        {/* Active Positions */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                📊 Live Virtual Positions
              </Typography>
              {positions?.length > 0 ? (
                <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Side</TableCell>
                        <TableCell align="right">PnL</TableCell>
                        <TableCell align="right">Age</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {positions.map((position, index) => (
                        <TableRow key={index}>
                          <TableCell>{position.symbol}</TableCell>
                          <TableCell>
                            <Chip
                              label={position.side}
                              color={position.side === 'LONG' ? 'success' : 'error'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              variant="body2"
                              color={getPnLColor(position.unrealized_pnl)}
                              fontWeight="bold"
                            >
                              ${position.unrealized_pnl?.toFixed(2)}
                              <br />
                              <Typography variant="caption" component="span">
                                ({position.unrealized_pnl_pct?.toFixed(1)}%)
                              </Typography>
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="caption">
                              {Math.floor(position.age_minutes)}m
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                  No active positions
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Daily Performance Chart */}
        {performance?.daily_performance && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  📈 Daily Learning Progress
                </Typography>
                <Grid container spacing={1}>
                  {performance.daily_performance.slice(-7).map((day, index) => (
                    <Grid item xs={12/7} key={index}>
                      <Box textAlign="center" p={1}>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(day.timestamp).toLocaleDateString('en-US', { weekday: 'short' })}
                        </Typography>
                        <Box
                          sx={{
                            height: 60,
                            display: 'flex',
                            alignItems: 'end',
                            justifyContent: 'center',
                            mb: 1
                          }}
                        >
                          <Box
                            sx={{
                              width: '80%',
                              height: `${Math.max(Math.abs(day.daily_pnl / 3), 10)}px`,
                              bgcolor: day.daily_pnl > 0 ? 'success.main' : 'error.main',
                              borderRadius: 1
                            }}
                          />
                        </Box>
                        <Typography
                          variant="caption"
                          fontWeight="bold"
                          color={day.daily_pnl > 0 ? 'success.main' : 'error.main'}
                        >
                          ${day.daily_pnl?.toFixed(0)}
                        </Typography>
                        <br />
                        <Typography variant="caption" color="text.secondary">
                          {day.total_trades} trades
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* ML Learning Insights */}
        {learningInsights && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight="bold" gutterBottom display="flex" alignItems="center" gap={1}>
                  <AIIcon color="primary" />
                  Advanced ML Learning Analytics
                </Typography>
                
                <Grid container spacing={3}>
                  {/* Market Regime Learning */}
                  <Grid item xs={12} md={6}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight="bold" color="primary" gutterBottom>
                        🌊 Market Regime Detection
                      </Typography>
                      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                        Accuracy: {learningInsights.market_regime_learning?.regime_detection_accuracy}%
                      </Typography>
                      {learningInsights.market_regime_learning?.regimes_identified.map((regime, index) => (
                        <Chip
                          key={index}
                          label={regime.replace('_', ' ')}
                          variant="outlined"
                          size="small"
                          sx={{ mr: 1, mb: 1 }}
                        />
                      ))}
                    </Box>
                  </Grid>

                  {/* Strategy Adaptation */}
                  <Grid item xs={12} md={6}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight="bold" color="success.main" gutterBottom>
                        🔄 Strategy Adaptation
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Success Rate: {learningInsights.strategy_adaptation?.adaptation_success_rate}%
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Successful: {learningInsights.strategy_adaptation?.successful_adaptations} | 
                        Failed: {learningInsights.strategy_adaptation?.failed_adaptations}
                      </Typography>
                    </Box>
                  </Grid>

                  {/* Learning Metrics */}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2" fontWeight="bold" color="info.main" gutterBottom>
                      📊 Learning Improvement Metrics
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="success.main" fontWeight="bold">
                            +{learningInsights.signal_quality?.signal_confidence_improvement}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Signal Confidence
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="success.main" fontWeight="bold">
                            -{learningInsights.signal_quality?.false_positive_reduction}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            False Positives
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="primary.main" fontWeight="bold">
                            {learningInsights.risk_learning?.leverage_adjustment_accuracy}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Risk Accuracy
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="info.main" fontWeight="bold">
                            {learningInsights.signal_quality?.signal_timing_accuracy}%
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Timing Accuracy
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>
                  </Grid>

                  {/* AI Recommendations */}
                  <Grid item xs={12}>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2" fontWeight="bold" color="warning.main" gutterBottom>
                      🤖 AI Recommendations
                    </Typography>
                    {learningInsights.recommendations?.map((rec, index) => (
                      <Typography key={index} variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                        • {rec}
                      </Typography>
                    ))}
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Learning Status Footer */}
      <Box mt={3} p={2} bgcolor="background.paper" borderRadius={2} border="1px solid" borderColor="divider">
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="body2" fontWeight="bold">
              🚀 Live Market Learning Status
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Learning from real market conditions • Building AI trading memory • Zero financial risk
            </Typography>
          </Box>
          <Box textAlign="right">
            <Typography variant="body2" color="primary" fontWeight="bold">
              Uptime: {status?.uptime_hours?.toFixed(1) || 0}h
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ML data points: {(status?.completed_trades * 50) || 0}
            </Typography>
          </Box>
        </Stack>
      </Box>
    </Box>
  );
};

export default PaperTrading; 