import React, { useState, useEffect } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  CircularProgress,
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import axios from 'axios';

function Dashboard() {
  const [pnl, setPnl] = useState(null);
  const [stats, setStats] = useState(null);
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('token');
        const headers = { Authorization: `Bearer ${token}` };

        const [pnlRes, statsRes, signalsRes] = await Promise.all([
          axios.get('http://localhost:8000/api/trading/pnl', { headers }),
          axios.get('http://localhost:8000/api/trading/stats', { headers }),
          axios.get('http://localhost:8000/api/trading/signals', { headers }),
        ]);

        setPnl(pnlRes.data);
        setStats(statsRes.data);
        setSignals(signalsRes.data.signals);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* PnL Overview */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              PnL Overview
            </Typography>
            <Box display="flex" justifyContent="space-between" mb={2}>
              <Typography variant="body1">
                Total PnL: ${pnl?.total_pnl.toFixed(2)}
              </Typography>
              <Typography variant="body1">
                Daily PnL: ${pnl?.daily_pnl.toFixed(2)}
              </Typography>
            </Box>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={pnl?.positions.map((pos) => ({
                  name: pos.symbol,
                  pnl: pos.pnl,
                }))}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="pnl"
                  stroke="#8884d8"
                  activeDot={{ r: 8 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </Grid>

      {/* Trading Statistics */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Trading Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Typography variant="subtitle2" color="textSecondary">
                    Total Trades
                  </Typography>
                  <Typography variant="h4">{stats?.total_trades}</Typography>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Typography variant="subtitle2" color="textSecondary">
                    Win Rate
                  </Typography>
                  <Typography variant="h4">
                    {(stats?.win_rate * 100).toFixed(1)}%
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Typography variant="subtitle2" color="textSecondary">
                    Avg Profit
                  </Typography>
                  <Typography variant="h4">
                    ${stats?.average_profit.toFixed(2)}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Typography variant="subtitle2" color="textSecondary">
                    Sharpe Ratio
                  </Typography>
                  <Typography variant="h4">
                    {stats?.sharpe_ratio.toFixed(2)}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>

      {/* Recent Signals */}
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Recent Trading Signals
            </Typography>
            <Grid container spacing={2}>
              {signals.map((signal, index) => (
                <Grid item xs={12} sm={6} md={4} key={index}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      bgcolor: 'background.default',
                      borderLeft: 4,
                      borderColor: signal.type === 'BUY' ? 'success.main' : 'error.main',
                    }}
                  >
                    <Typography variant="subtitle1">{signal.symbol}</Typography>
                    <Typography
                      variant="body2"
                      color={signal.type === 'BUY' ? 'success.main' : 'error.main'}
                    >
                      {signal.type} @ ${signal.price}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Confidence: {(signal.confidence * 100).toFixed(1)}%
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

export default Dashboard; 