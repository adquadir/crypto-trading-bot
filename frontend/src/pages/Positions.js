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
  Chip
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import axios from 'axios';
import config from '../config';

const Positions = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('pnl');
  const [sortOrder, setSortOrder] = useState('desc');
  const [lastUpdated, setLastUpdated] = useState(null);
  const maxRetries = 3;

  const handleError = (error) => {
    console.error('Error fetching positions:', error);
    let errorMessage = 'Failed to fetch positions';

    if (error.response) {
      // Server responded with error
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Positions endpoint not found. Please check the API configuration.';
          break;
        case 500:
          errorMessage = 'Server error. Please try again later.';
          break;
        default:
          errorMessage = `Server error: ${error.response.status}`;
      }
    } else if (error.request) {
      // Request made but no response
      errorMessage = 'No response from server. Please check your connection.';
    } else if (error.code === 'ECONNABORTED') {
      errorMessage = 'Request timed out. Please try again.';
    }

    setError(errorMessage);
  };

  const fetchPositions = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.POSITIONS}`, {
        timeout: 5000 // 5 second timeout
      });
      setPositions(response.data.positions || []);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchPositions, 5000);
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

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedPositions = positions
    .filter(position => 
      position.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      position.size.toString().includes(filter) ||
      position.entry_price.toString().includes(filter)
    )
    .sort((a, b) => {
      const multiplier = sortOrder === 'asc' ? 1 : -1;
      switch (sortBy) {
        case 'pnl':
          return (a.pnl - b.pnl) * multiplier;
        case 'size':
          return (a.size - b.size) * multiplier;
        case 'leverage':
          return (a.leverage - b.leverage) * multiplier;
        default:
          return 0;
      }
    });

  const getTotalPnL = () => {
    return positions.reduce((sum, pos) => sum + pos.pnl, 0);
  };

  if (loading && !positions.length) {
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
          Active Positions
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Chip
            label={`Total PnL: $${getTotalPnL().toFixed(2)}`}
            color={getTotalPnL() >= 0 ? 'success' : 'error'}
            icon={getTotalPnL() >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />}
          />
          <Tooltip title="Refresh positions">
            <IconButton onClick={fetchPositions} disabled={loading}>
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
              <Button color="inherit" size="small" onClick={fetchPositions}>
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
              label="Filter positions"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by symbol, size, or price..."
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
                <MenuItem value="pnl">PnL</MenuItem>
                <MenuItem value="size">Size</MenuItem>
                <MenuItem value="leverage">Leverage</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Box>

      {lastUpdated && (
        <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      )}

      <Grid container spacing={3}>
        {filteredAndSortedPositions.length === 0 ? (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="h6" color="textSecondary">
                {positions.length === 0 ? 'No active positions' : 'No positions match your filter'}
              </Typography>
            </Paper>
          </Grid>
        ) : (
          filteredAndSortedPositions.map((position) => (
            <Grid item xs={12} sm={6} md={4} key={position.symbol}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h6">{position.symbol}</Typography>
                    <Chip
                      label={`${position.pnl >= 0 ? '+' : ''}$${position.pnl.toFixed(2)}`}
                      color={position.pnl >= 0 ? 'success' : 'error'}
                      size="small"
                    />
                  </Box>
                  <Typography color="textSecondary">
                    Size: {position.size} BTC
                  </Typography>
                  <Typography color="textSecondary">
                    Entry: ${position.entry_price}
                  </Typography>
                  <Typography color="textSecondary">
                    Current: ${position.current_price}
                  </Typography>
                  <Typography color="textSecondary">
                    Leverage: {position.leverage}x
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );
};

export default Positions; 