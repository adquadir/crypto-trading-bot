import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  CircularProgress,
  Alert,
  Snackbar,
  Divider
} from '@mui/material';
import axios from 'axios';

const Settings = () => {
  const [settings, setSettings] = useState({
    maxPositionSize: '',
    maxLeverage: '',
    riskPerTrade: '',
    maxOpenTrades: '',
    maxCorrelation: '',
    minRiskReward: '',
    maxDailyLoss: '',
    maxDrawdown: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get('http://50.31.0.105:8000/api/trading/settings');
        setSettings(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch settings');
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await axios.post('http://50.31.0.105:8000/api/trading/settings', settings);
      setSuccess(true);
      setError(null);
    } catch (err) {
      setError('Failed to save settings');
      setSuccess(false);
    }
    setSaving(false);
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
        Trading Settings
      </Typography>
      
      {error && (
        <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        </Snackbar>
      )}

      {success && (
        <Snackbar open={success} autoHideDuration={6000} onClose={() => setSuccess(false)}>
          <Alert severity="success" onClose={() => setSuccess(false)}>
            Settings saved successfully
          </Alert>
        </Snackbar>
      )}

      <Card>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Risk Management
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Position Size"
                  name="maxPositionSize"
                  type="number"
                  value={settings.maxPositionSize}
                  onChange={handleChange}
                  inputProps={{ step: "0.01" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Leverage"
                  name="maxLeverage"
                  type="number"
                  value={settings.maxLeverage}
                  onChange={handleChange}
                  inputProps={{ step: "0.1" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Risk Per Trade (%)"
                  name="riskPerTrade"
                  type="number"
                  value={settings.riskPerTrade}
                  onChange={handleChange}
                  inputProps={{ step: "0.01" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Open Trades"
                  name="maxOpenTrades"
                  type="number"
                  value={settings.maxOpenTrades}
                  onChange={handleChange}
                />
              </Grid>

              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Advanced Settings
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Correlation"
                  name="maxCorrelation"
                  type="number"
                  value={settings.maxCorrelation}
                  onChange={handleChange}
                  inputProps={{ step: "0.01" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Min Risk/Reward"
                  name="minRiskReward"
                  type="number"
                  value={settings.minRiskReward}
                  onChange={handleChange}
                  inputProps={{ step: "0.1" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Daily Loss (%)"
                  name="maxDailyLoss"
                  type="number"
                  value={settings.maxDailyLoss}
                  onChange={handleChange}
                  inputProps={{ step: "0.01" }}
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Drawdown (%)"
                  name="maxDrawdown"
                  type="number"
                  value={settings.maxDrawdown}
                  onChange={handleChange}
                  inputProps={{ step: "0.01" }}
                />
              </Grid>

              <Grid item xs={12}>
                <Button
                  type="submit"
                  variant="contained"
                  color="primary"
                  disabled={saving}
                  sx={{ mt: 2 }}
                >
                  {saving ? <CircularProgress size={24} /> : 'Save Settings'}
                </Button>
              </Grid>
            </Grid>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Settings; 