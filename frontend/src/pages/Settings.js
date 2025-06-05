import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Snackbar,
  IconButton,
  Tooltip,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';
import config from '../config';

const Settings = () => {
  const [settings, setSettings] = useState({
    maxPositionSize: 0.1,
    maxLeverage: 3.0,
    riskPerTrade: 0.02,
    maxOpenTrades: 5,
    maxCorrelation: 0.7,
    minRiskReward: 2.0,
    maxDailyLoss: 0.05,
    maxDrawdown: 0.15,
    tradingEnabled: true,
    autoRebalance: false,
    stopLossEnabled: true,
    takeProfitEnabled: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error in settings:', error);
    let errorMessage = 'Failed to process settings';

    if (error.response) {
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Settings endpoint not found. Please check the API configuration.';
          break;
        case 500:
          errorMessage = 'Server error. Please try again later.';
          break;
        default:
          errorMessage = `Server error: ${error.response.status}`;
      }
    } else if (error.request) {
      errorMessage = 'No response from server. Please check your connection.';
    } else if (error.code === 'ECONNABORTED') {
      errorMessage = 'Request timed out. Please try again.';
    }

    setError(errorMessage);
  };

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.SETTINGS}`, {
        timeout: 5000
      });
      setSettings(response.data);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchSettings, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      await axios.post(`${config.API_BASE_URL}${config.ENDPOINTS.SETTINGS}`, settings, {
        timeout: 5000
      });
      setSuccess('Settings saved successfully');
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, [retryCount]);

  const handleChange = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const validateSettings = () => {
    const errors = [];
    if (settings.maxPositionSize <= 0) errors.push('Max position size must be greater than 0');
    if (settings.maxLeverage <= 0) errors.push('Max leverage must be greater than 0');
    if (settings.riskPerTrade <= 0 || settings.riskPerTrade > 1) errors.push('Risk per trade must be between 0 and 1');
    if (settings.maxOpenTrades <= 0) errors.push('Max open trades must be greater than 0');
    if (settings.maxCorrelation < 0 || settings.maxCorrelation > 1) errors.push('Max correlation must be between 0 and 1');
    if (settings.minRiskReward <= 0) errors.push('Min risk/reward must be greater than 0');
    if (settings.maxDailyLoss <= 0 || settings.maxDailyLoss > 1) errors.push('Max daily loss must be between 0 and 1');
    if (settings.maxDrawdown <= 0 || settings.maxDrawdown > 1) errors.push('Max drawdown must be between 0 and 1');
    return errors;
  };

  const handleSave = () => {
    const errors = validateSettings();
    if (errors.length > 0) {
      setError(errors.join(', '));
      return;
    }
    saveSettings();
  };

  if (loading && !settings) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          Trading Settings
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Tooltip title="Refresh settings">
            <IconButton onClick={fetchSettings} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            color="primary"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Snackbar 
          open={!!error} 
          autoHideDuration={6000} 
          onClose={() => setError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        </Snackbar>
      )}

      {success && (
        <Snackbar 
          open={!!success} 
          autoHideDuration={3000} 
          onClose={() => setSuccess(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert severity="success" onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        </Snackbar>
      )}

      {lastUpdated && (
        <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      )}

      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Trading Parameters
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Position Size"
              type="number"
              value={settings.maxPositionSize}
              onChange={handleChange('maxPositionSize')}
              inputProps={{ step: 0.01, min: 0 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Leverage"
              type="number"
              value={settings.maxLeverage}
              onChange={handleChange('maxLeverage')}
              inputProps={{ step: 0.1, min: 0 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Risk Per Trade"
              type="number"
              value={settings.riskPerTrade}
              onChange={handleChange('riskPerTrade')}
              inputProps={{ step: 0.01, min: 0, max: 1 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Open Trades"
              type="number"
              value={settings.maxOpenTrades}
              onChange={handleChange('maxOpenTrades')}
              inputProps={{ step: 1, min: 1 }}
            />
          </Grid>

          <Grid item xs={12}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="h6" gutterBottom>
              Risk Management
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Correlation"
              type="number"
              value={settings.maxCorrelation}
              onChange={handleChange('maxCorrelation')}
              inputProps={{ step: 0.1, min: 0, max: 1 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Min Risk/Reward"
              type="number"
              value={settings.minRiskReward}
              onChange={handleChange('minRiskReward')}
              inputProps={{ step: 0.1, min: 0 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Daily Loss"
              type="number"
              value={settings.maxDailyLoss}
              onChange={handleChange('maxDailyLoss')}
              inputProps={{ step: 0.01, min: 0, max: 1 }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Drawdown"
              type="number"
              value={settings.maxDrawdown}
              onChange={handleChange('maxDrawdown')}
              inputProps={{ step: 0.01, min: 0, max: 1 }}
            />
          </Grid>

          <Grid item xs={12}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="h6" gutterBottom>
              Trading Controls
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.tradingEnabled}
                  onChange={handleChange('tradingEnabled')}
                  color="primary"
                />
              }
              label="Enable Trading"
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.autoRebalance}
                  onChange={handleChange('autoRebalance')}
                  color="primary"
                />
              }
              label="Auto Rebalance"
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.stopLossEnabled}
                  onChange={handleChange('stopLossEnabled')}
                  color="primary"
                />
              }
              label="Enable Stop Loss"
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.takeProfitEnabled}
                  onChange={handleChange('takeProfitEnabled')}
                  color="primary"
                />
              }
              label="Enable Take Profit"
            />
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Settings; 