import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  Snackbar,
  Button
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import axios from 'axios';
import config from '../config';

const Signals = () => {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const maxRetries = 3;

  const fetchSignals = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.SIGNALS}`);
      setSignals(response.data.signals);
      setError(null);
      setRetryCount(0);
    } catch (err) {
      console.error('Error fetching signals:', err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchSignals, 5000);
      } else {
        setError('Failed to connect to server. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
    const ws = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.WS_SIGNALS}`);

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setWsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      const signal = JSON.parse(event.data);
      setSignals(prev => [signal, ...prev].slice(0, 100)); // Keep last 100 signals
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      setError('WebSocket connection error');
      setWsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket Disconnected');
      setWsConnected(false);
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        if (retryCount < maxRetries) {
          setRetryCount(prev => prev + 1);
        }
      }, 5000);
    };

    return () => {
      ws.close();
    };
  }, [retryCount]);

  const columns = [
    { field: 'timestamp', headerName: 'Time', width: 180 },
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    {
      field: 'signal',
      headerName: 'Signal',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={params.value === 'BUY' ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      field: 'confidence',
      headerName: 'Confidence',
      width: 120,
      renderCell: (params) => (
        <Typography>
          {(params.value * 100).toFixed(1)}%
        </Typography>
      ),
    },
    {
      field: 'indicators',
      headerName: 'Indicators',
      width: 300,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2">
            MACD: {params.value.macd.value.toFixed(2)}
          </Typography>
          <Typography variant="body2">
            RSI: {params.value.rsi}
          </Typography>
          <Typography variant="body2">
            BB: {params.value.bb.middle.toFixed(0)}
          </Typography>
        </Box>
      ),
    },
  ];

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Trading Signals
      </Typography>

      {!wsConnected && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          WebSocket disconnected. Attempting to reconnect...
        </Alert>
      )}
      
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
              <Button color="inherit" size="small" onClick={fetchSignals}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">Trading Signals</Typography>
              <Chip
                label={wsConnected ? 'Connected' : 'Disconnected'}
                color={wsConnected ? 'success' : 'error'}
                size="small"
              />
            </Box>
            <div style={{ height: 600, width: '100%' }}>
              <DataGrid
                rows={signals.map((signal, index) => ({
                  id: index,
                  ...signal,
                }))}
                columns={columns}
                pageSize={10}
                rowsPerPageOptions={[10]}
                disableSelectionOnClick
              />
            </div>
          </Paper>
        </Grid>

        {/* Latest Signal Details */}
        {signals.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Latest Signal Details
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle1">MACD Analysis</Typography>
                    <Typography variant="body2" color="textSecondary">
                      Value: {signals[0].indicators.macd.value.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Signal: {signals[0].indicators.macd.signal.toFixed(2)}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle1">Bollinger Bands</Typography>
                    <Typography variant="body2" color="textSecondary">
                      Upper: {signals[0].indicators.bb.upper.toFixed(0)}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Middle: {signals[0].indicators.bb.middle.toFixed(0)}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Lower: {signals[0].indicators.bb.lower.toFixed(0)}
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default Signals; 