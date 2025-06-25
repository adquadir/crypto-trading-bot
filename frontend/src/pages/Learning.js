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
      
      if (response.status === 404) {
        // Learning endpoints not yet implemented
        setLearningData({
          success: true,
          summary: {
            total_fakeouts: 0,
            total_virtual_golden: 0,
            false_negative_rate_pct: 0,
            max_rebound_pct: 0
          },
          learning_insights: {
            fakeouts_detected: [],
            virtual_golden_signals: []
          },
          dual_reality_enabled: false,
          implementation_status: "Learning system endpoints are being prepared. Coming soon!"
        });
        setError(null);
        return;
      }
      
      const data = await response.json();
      
      if (data.success) {
        setLearningData(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch learning insights');
      }
    } catch (err) {
      // Handle network errors gracefully
      setLearningData({
        success: true,
        summary: {
          total_fakeouts: 0,
          total_virtual_golden: 0,
          false_negative_rate_pct: 0,
          max_rebound_pct: 0
        },
        learning_insights: {
          fakeouts_detected: [],
          virtual_golden_signals: []
        },
        dual_reality_enabled: false,
        implementation_status: "Learning system endpoints are being prepared. Coming soon!"
      });
      setError(null);
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

      {/* Implementation Status Alert */}
      {learningData?.implementation_status && (
        <Alert severity="info" sx={{ mb: { xs: 2, sm: 3 } }}>
          <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">
            🚧 Learning System Status
          </Typography>
          <Typography variant="body2">
            {learningData.implementation_status}
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
                {learningData?.summary?.false_negative_rate_pct?.toFixed(1) || 0}%
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
                {((learningData?.summary?.max_rebound_pct || 0) * 100)?.toFixed(2)}%
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
                          ${fakeout.entry_price && !isNaN(fakeout.entry_price) ? 
                            fakeout.entry_price.toFixed(8) : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          ${fakeout.stop_loss && !isNaN(fakeout.stop_loss) ? 
                            fakeout.stop_loss.toFixed(8) : 'N/A'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={fakeout.rebound_pct && !isNaN(fakeout.rebound_pct) ? 
                            `+${(fakeout.rebound_pct * 100).toFixed(2)}%` : 
                            'N/A'
                          }
                          color={fakeout.rebound_pct && !isNaN(fakeout.rebound_pct) ? "success" : "default"}
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
                            {fakeout.created_at ? 
                              new Date(fakeout.created_at).toLocaleString() : 
                              'N/A'
                            }
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
                  <TableCell sx={{ fontWeight: 'bold' }}>Fakeouts</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual TP Hits</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Virtual Golden</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Avg Virtual Return</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Learning Outcome</TableCell>
                  {!isMobile && <TableCell sx={{ fontWeight: 'bold' }}>Insights</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {(() => {
                  // Process available data to create strategy comparison
                  const strategyData = {};
                  
                  // Process fakeouts
                  if (learningData?.learning_insights?.fakeouts_detected) {
                    learningData.learning_insights.fakeouts_detected.forEach(fakeout => {
                      const strategy = fakeout.strategy || 'unknown';
                      if (!strategyData[strategy]) {
                        strategyData[strategy] = {
                          strategy,
                          fakeouts: 0,
                          virtualTPs: 0,
                          virtualGolden: 0,
                          virtualReturns: [],
                          insights: []
                        };
                      }
                      strategyData[strategy].fakeouts++;
                      if (fakeout.virtual_tp_hit) {
                        strategyData[strategy].virtualTPs++;
                      }
                      if (fakeout.rebound_pct) {
                        strategyData[strategy].virtualReturns.push(fakeout.rebound_pct * 100);
                      }
                    });
                  }
                  
                  // Process virtual winners  
                  if (learningData?.learning_insights?.virtual_winners) {
                    learningData.learning_insights.virtual_winners.forEach(winner => {
                      const strategy = winner.strategy || 'unknown';
                      if (!strategyData[strategy]) {
                        strategyData[strategy] = {
                          strategy,
                          fakeouts: 0,
                          virtualTPs: 0,
                          virtualGolden: 0,
                          virtualReturns: [],
                          insights: []
                        };
                      }
                      strategyData[strategy].virtualTPs++;
                      if (winner.would_have_made_pct) {
                        strategyData[strategy].virtualReturns.push(winner.would_have_made_pct * 100);
                      }
                    });
                  }
                  
                  // Process virtual golden signals
                  if (learningData?.learning_insights?.virtual_golden_signals) {
                    learningData.learning_insights.virtual_golden_signals.forEach(golden => {
                      const strategy = golden.strategy || 'unknown';
                      if (!strategyData[strategy]) {
                        strategyData[strategy] = {
                          strategy,
                          fakeouts: 0,
                          virtualTPs: 0,
                          virtualGolden: 0,
                          virtualReturns: [],
                          insights: []
                        };
                      }
                      strategyData[strategy].virtualGolden++;
                    });
                  }
                  
                  const strategies = Object.values(strategyData);
                  
                  return strategies.length > 0 ? strategies.map((strategy, index) => {
                    const avgReturn = strategy.virtualReturns.length > 0 ? 
                      strategy.virtualReturns.reduce((a, b) => a + b, 0) / strategy.virtualReturns.length : 0;
                    
                    const totalActivity = strategy.fakeouts + strategy.virtualTPs + strategy.virtualGolden;
                    const learningOutcome = strategy.fakeouts > strategy.virtualTPs ? 'High Fakeout Risk' : 
                                          strategy.virtualTPs > 0 ? 'Learning Potential' : 'Needs More Data';
                    
                    return (
                      <TableRow key={index} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight="bold">
                            {strategy.strategy.replace('scalping_', '')}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={strategy.fakeouts}
                            color={strategy.fakeouts > 0 ? 'error' : 'default'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={strategy.virtualTPs}
                            color={strategy.virtualTPs > 0 ? 'success' : 'default'}
                            size="small"
                          />
                        </TableCell>
                      <TableCell>
                        <Chip 
                            label={strategy.virtualGolden}
                            color={strategy.virtualGolden > 0 ? 'warning' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                            label={avgReturn > 0 ? `+${avgReturn.toFixed(2)}%` : 'N/A'}
                            color={avgReturn > 0 ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                            label={learningOutcome}
                            color={learningOutcome === 'High Fakeout Risk' ? 'error' : 
                                   learningOutcome === 'Learning Potential' ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                        {!isMobile && (
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {totalActivity} total events
                            </Typography>
                          </TableCell>
                        )}
                    </TableRow>
                    );
                  }) : (
                    <TableRow>
                      <TableCell colSpan={isMobile ? 6 : 7} align="center">
                        <Typography color="text.secondary" py={2}>
                          No strategy comparison data yet. System is learning...
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })()}
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
                      {learningData?.summary?.total_signals || 0}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">False Negative Rate</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="error.main" fontWeight="bold">
                      {learningData?.summary?.false_negative_rate_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Virtual TP Hit Rate</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {learningData?.summary?.total_virtual_tps || 0} signals
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
                    <Typography variant="body2" color="text.secondary">Fakeouts Detected</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="warning.main" fontWeight="bold">
                      {learningData?.summary?.total_fakeouts || 0}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Maximum Rebound After SL</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {((learningData?.summary?.max_rebound_pct || 0) * 100).toFixed(2)}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          
          {/* Learning Quality Metrics */}
          <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mt: 2 }}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography variant="h6" gutterBottom>
                    🛡️ Data Corruption Prevention
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">Corruption Prevention Rate</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.corruption_prevention_rate_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">False Negatives Prevented</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="info.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.false_negatives_prevented || 0}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography variant="h6" gutterBottom>
                    🎯 Learning Quality
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">System Learning Status</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="primary.main" fontWeight="bold">
                      {learningData?.learning_insights?.learning_impact_metrics?.learning_quality || 'UNKNOWN'}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Learning Mode</Typography>
                    <Typography variant={isMobile ? "h5" : "h4"} color="success.main" fontWeight="bold">
                      {learningData?.summary?.learning_mode_active ? 'ACTIVE' : 'INACTIVE'}
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
              <strong>• True Performance:</strong> Learns from actual market behavior, not artificial exit points<br/>
              <strong>• Data Protection:</strong> Prevents {learningData?.learning_insights?.learning_impact_metrics?.false_negatives_prevented || 0} false negatives from corrupting learning data
            </Typography>
          </Alert>
        </TabPanel>
      </Card>
    </Container>
  );
} 