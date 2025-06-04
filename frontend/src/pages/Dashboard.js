import React, { useState, useEffect } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Alert,
  Snackbar,
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
import { API_CONFIG } from '../config';

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastSuccessfulFetch, setLastSuccessfulFetch] = useState(null);

  const MAX_RETRIES = 3;
  const RETRY_DELAY = 5000; // 5 seconds

  const handleError = (error, endpoint) => {
    console.error(`Error fetching ${endpoint}:`, error);
    
    let errorMessage = 'Failed to fetch data';
    if (error.code === 'ECONNREFUSED') {
      errorMessage = 'Cannot connect to server. Please check if the server is running.';
    } else if (error.code === 'ETIMEDOUT') {
      errorMessage = 'Connection timed out. Please check your internet connection.';
    } else if (error.response) {
      errorMessage = `Server error: ${error.response.status} - ${error.response.statusText}`;
    } else if (error.request) {
      errorMessage = 'No response from server. Please check your connection.';
    }

    setError({
      message: errorMessage,
      endpoint,
      timestamp: new Date().toISOString()
    });
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, pnlRes, positionsRes] = await Promise.all([
        axios.get(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.STATS}`),
        axios.get(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.PNL}`),
        axios.get(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.POSITIONS}`),
      ]);

      setStats(statsRes.data);
      setPnl(pnlRes.data);
      setPositions(positionsRes.data.positions);
      setError(null);
      setRetryCount(0);
      setLastSuccessfulFetch(new Date());
    } catch (error) {
      handleError(error, 'dashboard data');
      
      // Implement retry logic
      if (retryCount < MAX_RETRIES) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchData, RETRY_DELAY);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
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

  if (loading && !stats && !pnl && !positions.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Error Alert */}
      <Snackbar
        open={!!error}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" sx={{ width: '100%' }}>
          {error?.message}
          {retryCount > 0 && ` (Retry ${retryCount}/${MAX_RETRIES})`}
        </Alert>
      </Snackbar>

      {/* Last Update Time */}
      {lastSuccessfulFetch && (
        <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
          Last updated: {new Date(lastSuccessfulFetch).toLocaleTimeString()}
        </Typography>
      )}

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