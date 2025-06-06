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
  FormControlLabel,
  Slider,
  Card,
  CardContent,
  Tabs,
  Tab
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
    takeProfitEnabled: true,
    volatilityAdaptation: {
      enabled: true,
      sensitivity: 0.5,
      maxAdjustment: 0.3
    },
    performanceAdaptation: {
      enabled: true,
      winRateThreshold: 0.6,
      adjustmentFactor: 0.1
    },
    confidenceThresholds: {
      high: 0.8,
      medium: 0.6,
      low: 0.4
    }
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error:', error);
    let errorMessage = 'Failed to fetch settings';

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
      setSettings(response.data.settings || settings);
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
      const response = await axios.put(
        `${config.API_BASE_URL}${config.ENDPOINTS.SETTINGS}`,
        settings
      );
      if (response.data.success) {
        setSuccess('Settings saved successfully');
        setTimeout(() => setSuccess(null), 3000);
      }
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

  const handleNestedChange = (section, field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
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
          Settings
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          {lastUpdated && (
            <Typography variant="caption" color="textSecondary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
          <Tooltip title="Refresh settings">
            <IconButton onClick={fetchSettings} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={saving}
          >
            Save Changes
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
          <Alert
            severity="error"
            onClose={() => setError(null)}
          >
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
          <Alert
            severity="success"
            onClose={() => setSuccess(null)}
          >
            {success}
          </Alert>
        </Snackbar>
      )}

      <Tabs
        value={activeTab}
        onChange={(_, newValue) => setActiveTab(newValue)}
        sx={{ mb: 3 }}
      >
        <Tab label="Trading Parameters" />
        <Tab label="Risk Management" />
        <Tab label="Dynamic Adaptation" />
      </Tabs>

      {activeTab === 0 && (
        <Paper sx={{ p: 3 }}>
          <Grid container spacing={3}>
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
      )}

      {activeTab === 1 && (
        <Paper sx={{ p: 3 }}>
          <Grid container spacing={3}>
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
          </Grid>
        </Paper>
      )}

      {activeTab === 2 && (
        <Paper sx={{ p: 3 }}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Volatility Adaptation
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.volatilityAdaptation.enabled}
                    onChange={handleNestedChange('volatilityAdaptation', 'enabled')}
                    color="primary"
                  />
                }
                label="Enable Volatility Adaptation"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Sensitivity</Typography>
              <Slider
                value={settings.volatilityAdaptation.sensitivity}
                onChange={(_, value) => handleNestedChange('volatilityAdaptation', 'sensitivity')({ target: { value } })}
                min={0.1}
                max={1}
                step={0.1}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Max Adjustment</Typography>
              <Slider
                value={settings.volatilityAdaptation.maxAdjustment}
                onChange={(_, value) => handleNestedChange('volatilityAdaptation', 'maxAdjustment')({ target: { value } })}
                min={0.1}
                max={0.5}
                step={0.1}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="h6" gutterBottom>
                Performance Adaptation
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.performanceAdaptation.enabled}
                    onChange={handleNestedChange('performanceAdaptation', 'enabled')}
                    color="primary"
                  />
                }
                label="Enable Performance Adaptation"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Win Rate Threshold</Typography>
              <Slider
                value={settings.performanceAdaptation.winRateThreshold}
                onChange={(_, value) => handleNestedChange('performanceAdaptation', 'winRateThreshold')({ target: { value } })}
                min={0.5}
                max={0.8}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Adjustment Factor</Typography>
              <Slider
                value={settings.performanceAdaptation.adjustmentFactor}
                onChange={(_, value) => handleNestedChange('performanceAdaptation', 'adjustmentFactor')({ target: { value } })}
                min={0.05}
                max={0.2}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="h6" gutterBottom>
                Confidence Thresholds
              </Typography>
            </Grid>

            <Grid item xs={12} md={4}>
              <Typography gutterBottom>High Confidence</Typography>
              <Slider
                value={settings.confidenceThresholds.high}
                onChange={(_, value) => handleNestedChange('confidenceThresholds', 'high')({ target: { value } })}
                min={0.7}
                max={0.9}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <Typography gutterBottom>Medium Confidence</Typography>
              <Slider
                value={settings.confidenceThresholds.medium}
                onChange={(_, value) => handleNestedChange('confidenceThresholds', 'medium')({ target: { value } })}
                min={0.5}
                max={0.7}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <Typography gutterBottom>Low Confidence</Typography>
              <Slider
                value={settings.confidenceThresholds.low}
                onChange={(_, value) => handleNestedChange('confidenceThresholds', 'low')({ target: { value } })}
                min={0.3}
                max={0.5}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
};

export default Settings; 