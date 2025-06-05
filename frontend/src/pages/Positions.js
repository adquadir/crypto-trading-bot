import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Snackbar,
  Button
} from '@mui/material';
import axios from 'axios';
import config from '../config';

const Positions = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const maxRetries = 3;

  const fetchPositions = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.POSITIONS}`);
      setPositions(response.data);
      setError(null);
      setRetryCount(0);
    } catch (err) {
      console.error('Error fetching positions:', err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchPositions, 5000);
      } else {
        setError('Failed to connect to server. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, [retryCount]);

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
        Active Positions
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
              <Button color="inherit" size="small" onClick={fetchPositions}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Grid container spacing={3}>
        {positions.map((position) => (
          <Grid item xs={12} md={6} lg={4} key={position.id}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {position.symbol}
                </Typography>
                <Typography color="textSecondary">
                  Size: {position.size}
                </Typography>
                <Typography color="textSecondary">
                  Entry Price: ${position.entry_price}
                </Typography>
                <Typography color="textSecondary">
                  Current Price: ${position.current_price}
                </Typography>
                <Typography 
                  color={position.pnl >= 0 ? 'success.main' : 'error.main'}
                  variant="h6"
                >
                  PnL: ${position.pnl.toFixed(2)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default Positions; 