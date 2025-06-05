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
  Button
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
import config from '../config';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastSuccessfulFetch, setLastSuccessfulFetch] = useState(null);
  const maxRetries = 3;

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.STATS}`);
      setStats(response.data);
      setError(null);
      setRetryCount(0);
      setLastSuccessfulFetch(new Date());
    } catch (err) {
      console.error('Error fetching stats:', err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchStats, 5000); // Retry after 5 seconds
      } else {
        setError('Failed to connect to server. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, [retryCount]);

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
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.STATS}`),
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.PNL}`),
        axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.POSITIONS}`),
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
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchData, 5000);
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
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Trading Dashboard
      </Typography>

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
              <Button color="inherit" size="small" onClick={fetchStats}>
                Retry
              </Button>
            }
          >
            {error?.message}
            {retryCount > 0 && ` (Retry ${retryCount}/${maxRetries})`}
          </Alert>
        </Snackbar>
      )}

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
};

export default Dashboard; 