import React, { useState, useEffect, useRef } from 'react';
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
  Divider
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import axios from 'axios';
import config from '../config';

const Signals = () => {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [connectionDetails, setConnectionDetails] = useState({
    status: 'disconnected',
    lastError: null,
    reconnectAttempts: 0,
    lastConnected: null,
    latency: null
  });
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const missedHeartbeatsRef = useRef(0);
  const maxRetries = 3;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000; // 1 second
  const maxReconnectDelay = 30000; // 30 seconds
  const latencyTimeoutRef = useRef(null);

  const handleError = (error) => {
    console.error('Error in signals:', error);
    let errorMessage = 'Failed to fetch signals';

    if (error.response) {
      switch (error.response.status) {
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          break;
        case 403:
          errorMessage = 'Access denied. Please check your permissions.';
          break;
        case 404:
          errorMessage = 'Signals endpoint not found. Please check the API configuration.';
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

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.SIGNALS}`, {
        timeout: 5000
      });
      setSignals(response.data.signals || []);
      setError(null);
      setRetryCount(0);
      setLastUpdated(new Date());
    } catch (err) {
      handleError(err);
      if (retryCount < maxRetries) {
        setRetryCount(prev => prev + 1);
        setTimeout(fetchSignals, 5000);
      }
    } finally {
      setLoading(false);
    }
  };

  const calculateReconnectDelay = (attempt) => {
    // Exponential backoff with jitter
    const exponentialDelay = Math.min(
      baseReconnectDelay * Math.pow(2, attempt),
      maxReconnectDelay
    );
    const jitter = Math.random() * 1000; // Add up to 1 second of random jitter
    return exponentialDelay + jitter;
  };

  const updateConnectionStatus = (status, error = null) => {
    setConnectionDetails(prev => ({
      ...prev,
      status,
      lastError: error,
      lastUpdated: new Date()
    }));
  };

  const measureLatency = (ws) => {
    if (latencyTimeoutRef.current) {
      clearTimeout(latencyTimeoutRef.current);
    }

    const startTime = Date.now();
    try {
      ws.send(JSON.stringify({ type: 'ping', timestamp: startTime }));
      
      latencyTimeoutRef.current = setTimeout(() => {
        setConnectionDetails(prev => ({
          ...prev,
          latency: null // Reset latency if no response received
        }));
      }, 5000); // Timeout after 5 seconds
    } catch (err) {
      console.error('Error measuring latency:', err);
    }
  };

  const handleWebSocketError = (event) => {
    console.error('WebSocket Error:', event);
    const errorDetails = {
      code: event.code,
      reason: event.reason || 'Unknown error',
      timestamp: new Date()
    };

    let errorMessage = 'WebSocket connection error';
    if (event.code) {
      switch (event.code) {
        case 1000:
          errorMessage = 'Normal closure';
          break;
        case 1001:
          errorMessage = 'Going away - endpoint is going away';
          break;
        case 1002:
          errorMessage = 'Protocol error';
          break;
        case 1003:
          errorMessage = 'Unsupported data';
          break;
        case 1005:
          errorMessage = 'No status received';
          break;
        case 1006:
          errorMessage = 'Abnormal closure';
          break;
        case 1007:
          errorMessage = 'Invalid frame payload data';
          break;
        case 1008:
          errorMessage = 'Policy violation';
          break;
        case 1009:
          errorMessage = 'Message too big';
          break;
        case 1010:
          errorMessage = 'Missing extension';
          break;
        case 1011:
          errorMessage = 'Internal error';
          break;
        case 1012:
          errorMessage = 'Service restart';
          break;
        case 1013:
          errorMessage = 'Try again later';
          break;
        case 1014:
          errorMessage = 'Bad gateway';
          break;
        case 1015:
          errorMessage = 'TLS handshake error';
          break;
        default:
          errorMessage = `WebSocket error: ${event.code}`;
      }
    }

    updateConnectionStatus('error', { message: errorMessage, ...errorDetails });
    setError(errorMessage);

    if (event.code !== 1000) {
      reconnectWebSocket();
    }
  };

  const startHeartbeat = (ws) => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }

    heartbeatIntervalRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
          missedHeartbeatsRef.current = 0;
        } catch (err) {
          console.error('Error sending heartbeat:', err);
          missedHeartbeatsRef.current++;
          
          if (missedHeartbeatsRef.current >= maxMissedHeartbeats) {
            console.error('Too many missed heartbeats, reconnecting...');
            reconnectWebSocket();
          }
        }
      }
    }, heartbeatInterval);
  };

  const reconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    const currentAttempt = connectionDetails.reconnectAttempts + 1;
    const delay = calculateReconnectDelay(currentAttempt);

    updateConnectionStatus('reconnecting', {
      message: `Attempting to reconnect (${currentAttempt}/${maxReconnectAttempts})`,
      nextAttempt: new Date(Date.now() + delay)
    });

    reconnectTimeoutRef.current = setTimeout(() => {
      if (currentAttempt >= maxReconnectAttempts) {
        updateConnectionStatus('failed', {
          message: 'Maximum reconnection attempts reached',
          attempts: currentAttempt
        });
        return;
      }

      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        connectWebSocket();
      }
    }, delay);
  };

  const connectWebSocket = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.SIGNALS_WS}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket Connected');
        updateConnectionStatus('connected', null);
        setError(null);
        missedHeartbeatsRef.current = 0;
        setConnectionDetails(prev => ({
          ...prev,
          lastConnected: new Date(),
          reconnectAttempts: 0
        }));

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }

        startHeartbeat(ws);
        measureLatency(ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle heartbeat response
          if (data.type === 'pong') {
            missedHeartbeatsRef.current = 0;
            if (data.timestamp) {
              const latency = Date.now() - data.timestamp;
              setConnectionDetails(prev => ({
                ...prev,
                latency
              }));
            }
            return;
          }

          setSignals(prev => {
            const newSignals = [...prev, data];
            return newSignals.slice(-100);
          });
          setLastUpdated(new Date());
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = handleWebSocketError;

      ws.onclose = (event) => {
        console.log('WebSocket Disconnected:', event.code, event.reason);
        updateConnectionStatus('disconnected', {
          code: event.code,
          reason: event.reason
        });
        
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }
        
        if (latencyTimeoutRef.current) {
          clearTimeout(latencyTimeoutRef.current);
          latencyTimeoutRef.current = null;
        }
        
        if (event.code !== 1000) {
          reconnectWebSocket();
        }
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      updateConnectionStatus('error', {
        message: 'Failed to establish WebSocket connection',
        error: err.message
      });
      setError('Failed to establish WebSocket connection');
    }
  };

  useEffect(() => {
    fetchSignals();
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
    };
  }, []);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedSignals = signals
    .filter(signal => 
      signal.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      signal.strategy.toLowerCase().includes(filter.toLowerCase())
    )
    .sort((a, b) => {
      const multiplier = sortOrder === 'asc' ? 1 : -1;
      switch (sortBy) {
        case 'timestamp':
          return (new Date(a.timestamp) - new Date(b.timestamp)) * multiplier;
        case 'confidence':
          return (a.confidence - b.confidence) * multiplier;
        case 'price':
          return (a.price - b.price) * multiplier;
        default:
          return 0;
      }
    });

  if (loading && !signals.length) {
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
          Trading Signals
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Tooltip title={
            <Box>
              <Typography variant="body2">Status: {connectionDetails.status}</Typography>
              {connectionDetails.lastError && (
                <Typography variant="body2">Error: {connectionDetails.lastError.message}</Typography>
              )}
              {connectionDetails.lastConnected && (
                <Typography variant="body2">
                  Last Connected: {new Date(connectionDetails.lastConnected).toLocaleTimeString()}
                </Typography>
              )}
              {connectionDetails.latency && (
                <Typography variant="body2">
                  Latency: {connectionDetails.latency}ms
                </Typography>
              )}
              {connectionDetails.reconnectAttempts > 0 && (
                <Typography variant="body2">
                  Reconnect Attempts: {connectionDetails.reconnectAttempts}
                </Typography>
              )}
            </Box>
          }>
            <Chip
              label={`Connection: ${connectionDetails.status.toUpperCase()}`}
              color={
                connectionDetails.status === 'connected' ? 'success' :
                connectionDetails.status === 'error' ? 'error' :
                connectionDetails.status === 'reconnecting' ? 'warning' : 'default'
              }
            />
          </Tooltip>
          <Tooltip title="Refresh signals">
            <IconButton onClick={fetchSignals} disabled={loading}>
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
              <Button color="inherit" size="small" onClick={fetchSignals}>
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
              label="Filter signals"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by symbol or strategy..."
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
                <MenuItem value="timestamp">Time</MenuItem>
                <MenuItem value="confidence">Confidence</MenuItem>
                <MenuItem value="price">Price</MenuItem>
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
        {filteredAndSortedSignals.length === 0 ? (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="h6" color="textSecondary">
                {signals.length === 0 ? 'No signals available' : 'No signals match your filter'}
              </Typography>
            </Paper>
          </Grid>
        ) : (
          filteredAndSortedSignals.map((signal) => (
            <Grid item xs={12} sm={6} md={4} key={`${signal.symbol}-${signal.timestamp}`}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h6">{signal.symbol}</Typography>
                    <Chip
                      label={signal.action.toUpperCase()}
                      color={signal.action === 'buy' ? 'success' : 'error'}
                      size="small"
                    />
                  </Box>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Strategy
                      </Typography>
                      <Typography variant="body1">
                        {signal.strategy}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Confidence
                      </Typography>
                      <Typography variant="body1" color={signal.confidence >= 0.7 ? 'success.main' : 'warning.main'}>
                        {(signal.confidence * 100).toFixed(1)}%
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Price
                      </Typography>
                      <Typography variant="body1">
                        ${signal.price.toFixed(2)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Time
                      </Typography>
                      <Typography variant="body1">
                        {new Date(signal.timestamp).toLocaleTimeString()}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );
};

export default Signals; 