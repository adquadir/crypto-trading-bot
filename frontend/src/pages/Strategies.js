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
  Switch,
  FormControlLabel
} from '@mui/material';
import axios from 'axios';

const Strategies = () => {
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const response = await axios.get('http://50.31.0.105:8000/api/trading/strategies');
        setStrategies(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch strategies');
        setLoading(false);
      }
    };

    fetchStrategies();
  }, []);

  const handleStrategyToggle = async (strategyId, enabled) => {
    try {
      await axios.post(`http://50.31.0.105:8000/api/trading/strategies/${strategyId}/toggle`, {
        enabled
      });
      setStrategies(strategies.map(strategy => 
        strategy.id === strategyId ? { ...strategy, enabled } : strategy
      ));
    } catch (err) {
      setError('Failed to update strategy');
    }
  };

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
        Trading Strategies
      </Typography>
      
      {error && (
        <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        </Snackbar>
      )}

      <Grid container spacing={3}>
        {strategies.map((strategy) => (
          <Grid item xs={12} md={6} lg={4} key={strategy.id}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {strategy.name}
                </Typography>
                <Typography color="textSecondary" paragraph>
                  {strategy.description}
                </Typography>
                <Typography color="textSecondary" gutterBottom>
                  Performance: {strategy.performance}%
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={strategy.enabled}
                      onChange={(e) => handleStrategyToggle(strategy.id, e.target.checked)}
                      color="primary"
                    />
                  }
                  label={strategy.enabled ? "Enabled" : "Disabled"}
                />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default Strategies; 