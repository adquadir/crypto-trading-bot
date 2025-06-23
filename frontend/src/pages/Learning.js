import React, { useState, useEffect } from 'react';
import { Container, Grid, Card, CardContent, Typography, Box, Tabs, Tab, 
         Table, TableBody, TableCell, TableContainer, TableHead, TableRow, 
         Paper, Chip, Alert, CircularProgress } from '@mui/material';
import { Psychology as PsychologyIcon, TrendingUp as TrendingUpIcon, 
         Visibility as VisibilityIcon, CompareArrows as CompareArrowsIcon } from '@mui/icons-material';
import config from '../config';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function Learning() {
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
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress size={50} />
          <Typography variant="h6" sx={{ ml: 2 }}>Loading Learning Insights...</Typography>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Alert severity="error">
          <Typography variant="h6">Error Loading Learning Data</Typography>
          <Typography>{error}</Typography>
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom display="flex" alignItems="center">
          <PsychologyIcon sx={{ mr: 2, fontSize: 40, color: 'primary.main' }} />
          🧠 Intelligent Learning System
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Dual-Reality Tracking: Learning True Market Behavior, Not Just Stop Loss Outcomes
        </Typography>
      </Box>

      {/* Learning Status Alert */}
      {learningData?.dual_reality_enabled && (
        <Alert severity="success" sx={{ mb: 3 }}>
          <Typography variant="h6">🎯 Learning Mode Active</Typography>
          <Typography>
            System tracks virtual performance after stop loss hits to detect fakeouts and learn true signal quality.
          </Typography>
        </Alert>
      )}

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                🔥 Fakeouts Detected
              </Typography>
              <Typography variant="h4" color="error.main">
                {learningData?.summary?.total_fakeouts || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Stop losses that rebounded to profit
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                🌟 Virtual Golden Signals
              </Typography>
              <Typography variant="h4" color="success.main">
                {learningData?.summary?.total_virtual_golden || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Would have been golden without SL
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                📊 False Negatives
              </Typography>
              <Typography variant="h4" color="warning.main">
                {learningData?.learning_insights?.learning_impact_metrics?.false_negative_pct?.toFixed(1) || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Trades marked as losses incorrectly
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                💡 Max Rebound
              </Typography>
              <Typography variant="h4" color="info.main">
                {learningData?.learning_insights?.learning_impact_metrics?.max_rebound_after_sl?.toFixed(1) || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Best recovery after stop loss
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="🔥 Fakeout Detection" icon={<TrendingUpIcon />} />
            <Tab label="🌟 Virtual Golden Signals" icon={<VisibilityIcon />} />
            <Tab label="📊 Reality vs Virtual" icon={<CompareArrowsIcon />} />
            <Tab label="🎯 Learning Impact" icon={<PsychologyIcon />} />
          </Tabs>
        </Box>

        {/* Fakeout Detection Tab */}
        <TabPanel value={tabValue} index={0}>
          <Typography variant="h6" gutterBottom>
            🔥 Fakeout Detection - Stop Losses That Rebounded to Profit
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Strategy</TableCell>
                  <TableCell>Entry Price</TableCell>
                  <TableCell>Stop Loss</TableCell>
                  <TableCell>Rebound %</TableCell>
                  <TableCell>Virtual TP Hit</TableCell>
                  <TableCell>Learning Outcome</TableCell>
                  <TableCell>Time</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.fakeouts_detected?.length > 0 ? 
                  learningData.learning_insights.fakeouts_detected.map((fakeout, index) => (
                    <TableRow key={index}>
                      <TableCell><strong>{fakeout.symbol}</strong></TableCell>
                      <TableCell>{fakeout.strategy}</TableCell>
                      <TableCell>${fakeout.entry_price?.toFixed(4)}</TableCell>
                      <TableCell>${fakeout.stop_loss?.toFixed(4)}</TableCell>
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
                      <TableCell>{new Date(fakeout.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={8} align="center">
                        <Typography color="text.secondary">
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
          <Typography variant="h6" gutterBottom>
            🌟 Virtual Golden Signals - Would Have Been Golden Without Stop Loss
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Strategy</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Virtual Max Profit</TableCell>
                  <TableCell>SL Hit</TableCell>
                  <TableCell>Virtual TP Hit</TableCell>
                  <TableCell>Learning Outcome</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.virtual_golden_signals?.length > 0 ? 
                  learningData.learning_insights.virtual_golden_signals.map((signal, index) => (
                    <TableRow key={index}>
                      <TableCell><strong>{signal.symbol}</strong></TableCell>
                      <TableCell>{signal.strategy}</TableCell>
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
                        <Typography color="text.secondary">
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
          <Typography variant="h6" gutterBottom>
            📊 Reality vs Virtual Performance Comparison by Strategy
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Strategy</TableCell>
                  <TableCell>Total Signals</TableCell>
                  <TableCell>Actual SL Hits</TableCell>
                  <TableCell>Virtual TP Hits</TableCell>
                  <TableCell>Fakeouts</TableCell>
                  <TableCell>Actual Avg Return</TableCell>
                  <TableCell>Virtual Avg Return</TableCell>
                  <TableCell>Virtual Golden</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {learningData?.learning_insights?.strategy_reality_comparison?.length > 0 ? 
                  learningData.learning_insights.strategy_reality_comparison.map((strategy, index) => (
                    <TableRow key={index}>
                      <TableCell><strong>{strategy.strategy}</strong></TableCell>
                      <TableCell>{strategy.total_signals}</TableCell>
                      <TableCell>{strategy.actual_sl_hits}</TableCell>
                      <TableCell>{strategy.virtual_tp_hits}</TableCell>
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
                      <TableCell>{strategy.virtual_golden_count}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={8} align="center">
                        <Typography color="text.secondary">
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
          <Typography variant="h6" gutterBottom>
            🎯 Learning Impact Metrics (Last 24 Hours)
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🔬 Learning Statistics
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">Total Learning Signals</Typography>
                    <Typography variant="h4">{learningData?.learning_insights?.learning_impact_metrics?.total_learning_signals || 0}</Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">False Negative Rate</Typography>
                    <Typography variant="h4" color="error.main">
                      {learningData?.learning_insights?.learning_impact_metrics?.false_negative_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Would Have Won Rate</Typography>
                    <Typography variant="h4" color="success.main">
                      {learningData?.learning_insights?.learning_impact_metrics?.would_have_won_pct?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📈 Rebound Analysis
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">Average Rebound After SL</Typography>
                    <Typography variant="h4" color="info.main">
                      {learningData?.learning_insights?.learning_impact_metrics?.avg_rebound_after_sl?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Maximum Rebound After SL</Typography>
                    <Typography variant="h4" color="success.main">
                      {learningData?.learning_insights?.learning_impact_metrics?.max_rebound_after_sl?.toFixed(1) || 0}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          
          <Alert severity="info" sx={{ mt: 3 }}>
            <Typography variant="h6">🧠 How This Improves Your Trading</Typography>
            <Typography>
              • <strong>Fakeout Detection:</strong> Identifies when tight stop losses are getting hit by market noise, not real trends<br/>
              • <strong>Virtual Golden Signals:</strong> Discovers high-quality signals that were stopped out too early<br/>
              • <strong>Adaptive Stop Placement:</strong> System learns optimal stop loss distances for each strategy<br/>
              • <strong>True Performance:</strong> Learns from actual market behavior, not artificial exit points
            </Typography>
          </Alert>
        </TabPanel>
      </Card>
    </Container>
  );
} 