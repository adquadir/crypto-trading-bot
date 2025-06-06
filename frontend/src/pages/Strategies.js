import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Snackbar,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  Chip,
  Switch,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Slider,
  Divider
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import axios from 'axios';
import config from '../config';

const Strategies = () => {
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('win_rate');
  const [sortOrder, setSortOrder] = useState('desc');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [showInactive, setShowInactive] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [currentProfile, setCurrentProfile] = useState(null);
  const [editedProfile, setEditedProfile] = useState(null);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error:', error);
    let errorMessage = 'Failed to fetch strategies';

    if (error.response) {
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Strategies endpoint not found. Please check the API configuration.';
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

  const fetchStrategies = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.STRATEGIES}`, {
        timeout: 5000
      });
      setStrategies(response.data.strategies || []);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchStrategies, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEditProfile = (profile) => {
    setCurrentProfile(profile);
    setEditedProfile({ ...profile });
    setEditDialogOpen(true);
  };

  const handleSaveProfile = async () => {
    try {
      const response = await axios.put(
        `${config.API_BASE_URL}${config.ENDPOINTS.STRATEGIES}/${editedProfile.name}`,
        editedProfile
      );
      if (response.data.success) {
        setStrategies(prev =>
          prev.map(strat =>
            strat.name === editedProfile.name ? editedProfile : strat
          )
        );
        setEditDialogOpen(false);
      }
    } catch (err) {
      handleError(err);
    }
  };

  const handleParameterChange = (param, value) => {
    setEditedProfile(prev => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [param]: value
      }
    }));
  };

  useEffect(() => {
    fetchStrategies();
    const interval = setInterval(fetchStrategies, 30000);
    return () => clearInterval(interval);
  }, [retryCount]);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedStrategies = strategies
    .filter(strategy =>
      (showInactive || strategy.active) &&
      strategy.name.toLowerCase().includes(filter.toLowerCase())
    )
    .sort((a, b) => {
      const multiplier = sortOrder === 'asc' ? 1 : -1;
      switch (sortBy) {
        case 'win_rate':
          return (a.performance.win_rate - b.performance.win_rate) * multiplier;
        case 'profit_factor':
          return (a.performance.profit_factor - b.performance.profit_factor) * multiplier;
        case 'sharpe_ratio':
          return (a.performance.sharpe_ratio - b.performance.sharpe_ratio) * multiplier;
        default:
          return 0;
      }
    });

  const getAverageWinRate = () => {
    if (!strategies.length) return 0;
    const total = strategies.reduce((sum, strat) => sum + strat.performance.win_rate, 0);
    return total / strategies.length;
  };

  if (loading && !strategies.length) {
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
          Trading Strategies
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Chip
            label={`Avg Win Rate: ${(getAverageWinRate() * 100).toFixed(1)}%`}
            color={getAverageWinRate() >= 0.5 ? 'success' : 'error'}
            icon={getAverageWinRate() >= 0.5 ? <TrendingUpIcon /> : <TrendingDownIcon />}
          />
          <Tooltip title="Refresh strategies">
            <IconButton onClick={fetchStrategies} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
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
            action={
              <Button color="inherit" size="small" onClick={fetchStrategies}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Box mb={3}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Filter strategies"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by strategy name..."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Sort by</InputLabel>
              <Select
                value={sortBy}
                label="Sort by"
                onChange={(e) => handleSort(e.target.value)}
              >
                <MenuItem value="win_rate">Win Rate</MenuItem>
                <MenuItem value="profit_factor">Profit Factor</MenuItem>
                <MenuItem value="sharpe_ratio">Sharpe Ratio</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControlLabel
              control={
                <Switch
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                />
              }
              label="Show Inactive Strategies"
            />
          </Grid>
        </Grid>
      </Box>

      {lastUpdated && (
        <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      )}

      <Grid container spacing={2}>
        {filteredAndSortedStrategies.length === 0 ? (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="h6" color="textSecondary">
                {strategies.length === 0 ? 'No strategies available' : 'No strategies match your filter'}
              </Typography>
            </Paper>
          </Grid>
        ) : (
          filteredAndSortedStrategies.map((strategy) => (
            <Grid item xs={12} sm={6} md={4} key={strategy.name}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h6">{strategy.name}</Typography>
                    <Box>
                      <Tooltip title="Edit Strategy">
                        <IconButton
                          size="small"
                          onClick={() => handleEditProfile(strategy)}
                        >
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={strategy.active}
                            onChange={() => toggleStrategy(strategy.name, strategy.active)}
                            color="primary"
                          />
                        }
                        label={strategy.active ? 'Active' : 'Inactive'}
                      />
                    </Box>
                  </Box>

                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Win Rate
                      </Typography>
                      <Typography variant="h6" color={strategy.performance.win_rate >= 0.5 ? 'success.main' : 'error.main'}>
                        {(strategy.performance.win_rate * 100).toFixed(1)}%
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Profit Factor
                      </Typography>
                      <Typography variant="h6" color={strategy.performance.profit_factor >= 1 ? 'success.main' : 'error.main'}>
                        {strategy.performance.profit_factor.toFixed(2)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Sharpe Ratio
                      </Typography>
                      <Typography variant="h6" color={strategy.performance.sharpe_ratio >= 1 ? 'success.main' : 'error.main'}>
                        {strategy.performance.sharpe_ratio.toFixed(2)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Volatility Factor
                      </Typography>
                      <Typography variant="h6">
                        {strategy.parameters.volatility_factor.toFixed(2)}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>

      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Edit Strategy Profile: {currentProfile?.name}
        </DialogTitle>
        <DialogContent>
          {editedProfile && (
            <Box sx={{ mt: 2 }}>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Typography variant="h6" gutterBottom>
                    Technical Indicators
                  </Typography>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>MACD Fast Period</Typography>
                  <Slider
                    value={editedProfile.parameters.macd_fast_period}
                    onChange={(_, value) => handleParameterChange('macd_fast_period', value)}
                    min={5}
                    max={20}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>MACD Slow Period</Typography>
                  <Slider
                    value={editedProfile.parameters.macd_slow_period}
                    onChange={(_, value) => handleParameterChange('macd_slow_period', value)}
                    min={15}
                    max={40}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>RSI Overbought</Typography>
                  <Slider
                    value={editedProfile.parameters.rsi_overbought}
                    onChange={(_, value) => handleParameterChange('rsi_overbought', value)}
                    min={60}
                    max={90}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>RSI Oversold</Typography>
                  <Slider
                    value={editedProfile.parameters.rsi_oversold}
                    onChange={(_, value) => handleParameterChange('rsi_oversold', value)}
                    min={10}
                    max={40}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    Risk Management
                  </Typography>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>Max Position Size</Typography>
                  <Slider
                    value={editedProfile.parameters.max_position_size}
                    onChange={(_, value) => handleParameterChange('max_position_size', value)}
                    min={0.01}
                    max={0.5}
                    step={0.01}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>Max Leverage</Typography>
                  <Slider
                    value={editedProfile.parameters.max_leverage}
                    onChange={(_, value) => handleParameterChange('max_leverage', value)}
                    min={1}
                    max={20}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>Risk Per Trade</Typography>
                  <Slider
                    value={editedProfile.parameters.risk_per_trade}
                    onChange={(_, value) => handleParameterChange('risk_per_trade', value)}
                    min={0.01}
                    max={0.05}
                    step={0.01}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <Typography gutterBottom>Confidence Threshold</Typography>
                  <Slider
                    value={editedProfile.parameters.confidence_threshold}
                    onChange={(_, value) => handleParameterChange('confidence_threshold', value)}
                    min={0.5}
                    max={0.9}
                    step={0.05}
                    marks
                    valueLabelDisplay="auto"
                  />
                </Grid>
              </Grid>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSaveProfile}
            variant="contained"
            startIcon={<SaveIcon />}
          >
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Strategies; 