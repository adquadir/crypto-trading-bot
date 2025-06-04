import React, { useState, useEffect } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
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
  const [stats, setStats] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [positions, setPositions] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, pnlRes, positionsRes] = await Promise.all([
          axios.get('http://localhost:8000/api/trading/stats'),
          axios.get('http://localhost:8000/api/trading/pnl'),
          axios.get('http://localhost:8000/api/trading/positions'),
        ]);

        setStats(statsRes.data);
        setPnl(pnlRes.data);
        setPositions(positionsRes.data.positions);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const StatCard = ({ title, value, subtitle }) => (
    <Card>
      <CardContent>
        <Typography color="textSecondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4" component="div">
          {value}
        </Typography>
        {subtitle && (
          <Typography color="textSecondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Performance Stats */}
        <Grid item xs={12} md={3}>
          <StatCard
            title="Total PnL"
            value={`$${pnl?.total_pnl?.toFixed(2) || '0.00'}`}
            subtitle={`Daily: $${pnl?.daily_pnl?.toFixed(2) || '0.00'}`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Win Rate"
            value={`${stats?.win_rate ? (stats.win_rate * 100).toFixed(1) : '0'}%`}
            subtitle={`Total Trades: ${stats?.total_trades || 0}`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Profit Factor"
            value={stats?.profit_factor?.toFixed(2) || '0.00'}
            subtitle={`Sharpe: ${stats?.sharpe_ratio?.toFixed(2) || '0.00'}`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Max Drawdown"
            value={`${stats?.max_drawdown ? (stats.max_drawdown * 100).toFixed(1) : '0'}%`}
            subtitle={`Open Positions: ${positions.length}`}
          />
        </Grid>

        {/* PnL Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Performance History
            </Typography>
            <Box sx={{ height: 400 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={[
                    { time: '00:00', pnl: 0 },
                    { time: '04:00', pnl: 500 },
                    { time: '08:00', pnl: 1200 },
                    { time: '12:00', pnl: 800 },
                    { time: '16:00', pnl: 1500 },
                    { time: '20:00', pnl: 2000 },
                  ]}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="pnl"
                    stroke="#8884d8"
                    name="PnL"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Active Positions */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Active Positions
            </Typography>
            <Grid container spacing={2}>
              {positions.map((position) => (
                <Grid item xs={12} sm={6} md={4} key={position.symbol}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6">{position.symbol}</Typography>
                      <Typography color="textSecondary">
                        Size: {position.size} BTC
                      </Typography>
                      <Typography color="textSecondary">
                        Entry: ${position.entry_price}
                      </Typography>
                      <Typography color="textSecondary">
                        Current: ${position.current_price}
                      </Typography>
                      <Typography
                        color={position.pnl >= 0 ? 'success.main' : 'error.main'}
                      >
                        PnL: ${position.pnl.toFixed(2)}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Dashboard; 