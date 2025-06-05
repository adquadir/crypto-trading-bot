import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Snackbar
} from '@mui/material';
import axios from 'axios';

const Positions = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const response = await axios.get('http://50.31.0.105:8000/api/trading/positions');
        setPositions(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch positions');
        setLoading(false);
      }
    };

    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, []);

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
        <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
          <Alert severity="error" onClose={() => setError(null)}>
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