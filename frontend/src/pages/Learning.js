import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Grid, 
  Card, 
  CardContent, 
  Typography, 
  Box, 
  Tabs, 
  Tab, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  Paper, 
  Chip, 
  Alert, 
  CircularProgress,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { 
  Psychology as PsychologyIcon, 
  TrendingUp as TrendingUpIcon, 
  Visibility as VisibilityIcon, 
  CompareArrows as CompareArrowsIcon 
} from '@mui/icons-material';
import config from '../config';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: { xs: 2, sm: 3 } }}>{children}</Box>}
    </div>
  );
}

export default function Learning() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

  const [tabValue, setTabValue] = useState(0);
  const [learningData, setLearningData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchLearningInsights();
  }, []);

  const fetchLearningInsights = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${config.API_BASE_URL}/api/v1/trading/learning-insights`);
      const data = await response.json();
      
      if (data.success) {
        setLearningData(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch learning insights');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: { xs: 1, sm: 2, md: 3 } }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress size={isMobile ? 40 : 60} />
          {!isMobile && (
            <Typography variant="h6" sx={{ ml: 2 }}>
              Loading Learning Insights...
            </Typography>
          )}
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="xl" sx={{ py: { xs: 1, sm: 2, md: 3 } }}>
        <Alert severity="error">
          <Typography variant="h6">Error Loading Learning Data</Typography>
          <Typography>{error}</Typography>
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: { xs: 1, sm: 2, md: 3 } }}>
      {/* Mobile-Optimized Header */}
      <Box sx={{ mb: { xs: 2, sm: 3, md: 4 } }}>
        <Box display="flex" alignItems="center" mb={1} flexWrap="wrap" gap={1}>
          <PsychologyIcon 
            sx={{ 
              fontSize: { xs: 32, sm: 40 }, 
              color: 'primary.main',
              mr: { xs: 1, sm: 2 }
            }} 
          />
          <Typography 
            variant={isMobile ? "h5" : "h4"} 
            fontWeight="bold"
            sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
          >
            🧠 Intelligent Learning System
          </Typography>
        </Box>
        <Typography 
          variant="subtitle1" 
          color="text.secondary"
          sx={{ 
            fontSize: { xs: '0.875rem', sm: '1rem' },
            ml: { xs: 0, sm: 6 }
          }}
        >
          Dual-Reality Tracking: Learning True Market Behavior, Not Just Stop Loss Outcomes
        </Typography>
      </Box>

      {/* Learning Status Alert */}
      {learningData?.dual_reality_enabled && (
        <Alert severity="success" sx={{ mb: { xs: 2, sm: 3 } }}>
          <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">
            🎯 Learning Mode Active
          </Typography>
          <Typography variant="body2">
            System tracks virtual performance after stop loss hits to detect fakeouts and learn true signal quality.
          </Typography>
        </Alert>
      )}

      {/* Mobile-Optimized Summary Cards */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: { xs: 2, sm: 3, md: 4 } }}>
        <Grid item xs={6} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
              <Typography 
                color="text.secondary" 
                gutterBottom 
                variant={isMobile ? "caption" : "body2"}
                sx={{ fontSize: { xs: '0.625rem', sm: '0.875rem' } }}
              >
                🔥 Fakeouts Detected
              </Typography>
              <Typography 
                variant={isMobile ? "h5" : "h4"} 
                color="error.main" 
                fontWeight="bold"
              >
                {learningData?.summary?.total_fakeouts || 0}
              </Typography>
              <Typography 
                variant="caption" 
                color="text.secondary"
                sx={{ fontSize: { xs: '0.625rem', sm: '0.75rem' } }}
              >
                Stop losses that rebounded to profit
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
              <Typography 
                color="text.secondary" 
                gutterBottom 
                variant={isMobile ? "caption" : "body2"}
                sx={{ fontSize: { xs: '0.625rem', sm: '0.875rem' } }}
              >
                🌟 Virtual Golden Signals
              </Typography>
              <Typography 
                variant={isMobile ? "h5" : "h4"} 
                color="success.main" 
                fontWeight="bold"
              >
                {learningData?.summary?.total_virtual_golden || 0}
              </Typography>
              <Typography 
                variant="caption" 
                color="text.secondary"
                sx={{ fontSize: { xs: '0.625rem', sm: '0.75rem' } }}
              >
                Would have been golden without SL
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
              <Typography 
                color="text.secondary" 
                gutterBottom 
                variant={isMobile ? "caption" : "body2"}
                sx={{ fontSize: { xs: '0.625rem', sm: '0.875rem' } }}
              >
                📊 False Negatives
              </Typography>
              <Typography 
                variant={isMobile ? "h5" : "h4"} 
                color="warning.main" 
                fontWeight="bold"
              >
                {learningData?.learning_insights?.learning_impact_metrics?.false_negative_pct?.toFixed(1) || 0}%
              </Typography>
              <Typography 
                variant="caption" 
                color="text.secondary"
                sx={{ fontSize: { xs: '0.625rem', sm: '0.75rem' } }}
              >
                Trades marked as losses incorrectly
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: { xs: 1.5, sm: 2 } }}>
              <Typography 
                color="text.secondary" 
                gutterBottom 
                variant={isMobile ? "caption" : "body2"}
                sx={{ fontSize: { xs: '0.625rem', sm: '0.875rem' } }}
              >
                💡 Max Rebound
              </Typography>
              <Typography 
                variant={isMobile ? "h5" : "h4"} 
                color="info.main" 
                fontWeight="bold"
              >
                {learningData?.learning_insights?.learning_impact_metrics?.max_rebound_after_sl?.toFixed(1) || 0}%
              </Typography>
              <Typography 
                variant="caption" 
                color="text.secondary"
                sx={{ fontSize: { xs: '0.625rem', sm: '0.75rem' } }}
              >
                Best recovery after stop loss
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Mobile-Optimized Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
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
            <Tab 
              label={isMobile ? "🔥 Fakeouts" : "🔥 Fakeout Detection"} 
              icon={isMobile ? null : <TrendingUpIcon />} 
            />
            <Tab 
              label={isMobile ? "🌟 Virtual" : "🌟 Virtual Golden Signals"} 
              icon={isMobile ? null : <VisibilityIcon />} 
            />
            <Tab 
              label={isMobile ? "📊 Compare" : "📊 Reality vs Virtual"} 
              icon={isMobile ? null : <CompareArrowsIcon />} 
            />
            <Tab 
              label={isMobile ? "🎯 Impact" : "🎯 Learning Impact"} 
              icon={isMobile ? null : <PsychologyIcon />} 
            />
          </Tabs>
        </Box>

        {/* Fakeout Detection Tab */}
        <TabPanel value={tabValue} index={0}>
          <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
            🔥 Fakeout Detection - Stop Losses That Rebounded to Profit
          </Typography>
          <TableContainer 
            component={Paper} 
            sx={{ 
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
            }}
          >
            <Table size={isMobile ? "small" : "medium"}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Strategy</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Entry Price</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Stop Loss</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Rebound %</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual TP Hit</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Learning Outcome</TableCell>
                  {!isMobile && <TableCell sx={{ fontWeight: 'bold' }}>Time</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.fakeouts_detected?.length > 0 ? 
                  learningData.learning_insights.fakeouts_detected.map((fakeout, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {fakeout.symbol}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {fakeout.strategy}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          ${fakeout.entry_price?.toFixed(4)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          ${fakeout.stop_loss?.toFixed(4)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={`+${(fakeout.post_sl_peak_pct * 100)?.toFixed(1)}%`}
                          color="success"
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {fakeout.virtual_tp_hit ? 
                          <Chip label="✅ YES" color="success" size="small" /> : 
                          <Chip label="❌ NO" color="default" size="small" />
                        }
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={fakeout.learning_outcome} 
                          color={fakeout.learning_outcome === 'false_negative' ? 'error' : 'success'}
                          size="small" 
                        />
                      </TableCell>
                      {!isMobile && (
                        <TableCell>
                          <Typography variant="caption">
                            {new Date(fakeout.timestamp).toLocaleString()}
                          </Typography>
                        </TableCell>
                      )}
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={isMobile ? 7 : 8} align="center">
                        <Typography color="text.secondary" py={2}>
                          No fakeouts detected yet. System is learning...
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )
                }
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        {/* Virtual Golden Signals Tab */}
        <TabPanel value={tabValue} index={1}>
          <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
            🌟 Virtual Golden Signals - Would Have Been Golden Without Stop Loss
          </Typography>
          <TableContainer 
            component={Paper}
            sx={{ 
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
            }}
          >
            <Table size={isMobile ? "small" : "medium"}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Strategy</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Confidence</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual Max Profit</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>SL Hit</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual TP Hit</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Learning Outcome</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.virtual_golden_signals?.length > 0 ? 
                  learningData.learning_insights.virtual_golden_signals.map((signal, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
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
                          label={`${(signal.confidence * 100)?.toFixed(0)}%`}
                          color="primary"
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={`+${(signal.virtual_max_profit_pct * 100)?.toFixed(1)}%`}
                          color="success"
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {signal.stop_loss_hit ? 
                          <Chip label="🛑 YES" color="error" size="small" /> : 
                          <Chip label="✅ NO" color="success" size="small" />
                        }
                      </TableCell>
                      <TableCell>
                        {signal.virtual_tp_hit ? 
                          <Chip label="🎯 YES" color="success" size="small" /> : 
                          <Chip label="❌ NO" color="default" size="small" />
                        }
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={signal.learning_outcome || 'Learning...'} 
                          color="info"
                          size="small" 
                        />
                      </TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={7} align="center">
                        <Typography color="text.secondary" py={2}>
                          No virtual golden signals yet. System is learning...
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )
                }
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        {/* Reality vs Virtual Tab */}
        <TabPanel value={tabValue} index={2}>
          <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
            📊 Reality vs Virtual Performance Comparison by Strategy
          </Typography>
          <TableContainer 
            component={Paper}
            sx={{ 
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
            }}
          >
            <Table size={isMobile ? "small" : "medium"}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Strategy</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Total Signals</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Actual SL Hits</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual TP Hits</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Fakeouts</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Actual Avg Return</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual Avg Return</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual Golden</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.strategy_reality_comparison?.length > 0 ? 
                  learningData.learning_insights.strategy_reality_comparison.map((strategy, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {strategy.strategy}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {strategy.total_signals}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {strategy.actual_sl_hits}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {strategy.virtual_tp_hits}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={strategy.fakeouts_detected}
                          color={strategy.fakeouts_detected > 0 ? 'warning' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={`${strategy.actual_avg_return?.toFixed(1)}%`}
                          color={strategy.actual_avg_return > 0 ? 'success' : 'error'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={`${strategy.virtual_avg_return?.toFixed(1)}%`}
                          color={strategy.virtual_avg_return > 0 ? 'success' : 'error'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {strategy.virtual_golden_count}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={8} align="center">
                        <Typography color="text.secondary" py={2}>
                          No strategy comparison data yet. System is learning...
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )
                }
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        {/* Learning Impact Tab */}
        <TabPanel value={tabValue} index={3}>
          <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
            🎯 Learning Impact Metrics (Last 24 Hours)
          </Typography>
          <Grid container spacing={{ xs: 2, sm: 3 }}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography variant="h6" gutterBottom>
                    🔬 Learning Statistics
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">Total Learning Signals</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.total_learning_signals || 0}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">False Negative Rate</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="error.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.false_negative_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Would Have Won Rate</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.would_have_won_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography variant="h6" gutterBottom>
                    📈 Rebound Analysis
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">Average Rebound After SL</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="info.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.avg_rebound_after_sl?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Maximum Rebound After SL</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.max_rebound_after_sl?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          
          <Alert severity="info" sx={{ mt: 3 }}>
            <Typography variant="h6" sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
              🧠 How This Improves Your Trading
            </Typography>
            <Typography variant="body2">
              <strong>• Fakeout Detection:</strong> Identifies when tight stop losses are getting hit by market noise, not real trends<br/>
              <strong>• Virtual Golden Signals:</strong> Discovers high-quality signals that were stopped out too early<br/>
              <strong>• Adaptive Stop Placement:</strong> System learns optimal stop loss distances for each strategy<br/>
              <strong>• True Performance:</strong> Learns from actual market behavior, not artificial exit points
            </Typography>
          </Alert>
        </TabPanel>
      </Card>
    </Container>
  );
} 