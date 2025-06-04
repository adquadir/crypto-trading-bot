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
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';

function Signals() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    // Initial signals fetch
    const fetchSignals = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/trading/signals');
        const data = await response.json();
        setSignals(data.signals);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching signals:', error);
        setLoading(false);
      }
    };

    fetchSignals();

    // WebSocket connection for real-time updates
    const ws = new WebSocket('ws://localhost:8000/ws/signals');

    ws.onopen = () => {
      console.log('WebSocket Connected');
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      const signal = JSON.parse(event.data);
      setSignals((prevSignals) => [signal, ...prevSignals].slice(0, 100)); // Keep last 100 signals
    };

    ws.onclose = () => {
      console.log('WebSocket Disconnected');
      setWsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

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
    <Box>
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
}

export default Signals; 