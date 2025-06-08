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
  Divider,
  CardHeader,
  List,
  ListItem,
  ListItemText
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
  const maxMissedHeartbeats = 3; // Maximum number of missed heartbeats before reconnecting
  const heartbeatInterval = 30000; // Heartbeat interval in milliseconds (30 seconds)
  const connectionTimeoutRef = useRef(null);

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
        timeout: 5000,
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Ensure signals have the required structure
      const processedSignals = (response.data.signals || []).map(signal => ({
        ...signal,
        indicators: signal.indicators || {
          macd: { value: 0, signal: 0 },
          rsi: 0,
          bb: { upper: 0, middle: 0, lower: 0 }
        }
      }));
      
      setSignals(processedSignals);
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
          const timestamp = Date.now();
          ws.send(JSON.stringify({ 
            type: 'ping',
            timestamp
          }));
          missedHeartbeatsRef.current = 0;
        } catch (err) {
          console.error('Error sending heartbeat:', err);
          missedHeartbeatsRef.current++;
          
          if (missedHeartbeatsRef.current >= maxMissedHeartbeats) {
            console.error('Too many missed heartbeats, reconnecting...');
            reconnectWebSocket();
          }
        }
      } else if (ws.readyState === WebSocket.CLOSED) {
        console.error('WebSocket is closed, attempting to reconnect...');
        reconnectWebSocket();
      }
    }, heartbeatInterval);
  };

  const reconnectWebSocket = () => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (err) {
        console.error('Error closing WebSocket:', err);
      }
      wsRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
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

      connectWebSocket();
    }, delay);
  };

  const connectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.WS_SIGNALS}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnectionDetails(prev => ({
        ...prev,
        status: 'connected',
        lastConnected: new Date(),
        reconnectAttempts: 0,
        lastError: null
      }));
      setError(null);
      missedHeartbeatsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'heartbeat') {
          missedHeartbeatsRef.current = 0;
          setConnectionDetails(prev => ({
            ...prev,
            latency: Date.now() - data.timestamp
          }));
        } else if (data.type === 'signal_update') {
          setSignals(prev => {
            const updated = [...prev];
            const index = updated.findIndex(s => s.symbol === data.signal.symbol);
            if (index >= 0) {
              updated[index] = data.signal;
            } else {
              updated.push(data.signal);
            }
            return updated;
          });
          setLastUpdated(new Date());
        }
      } catch (err) {
        console.error('Error processing WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionDetails(prev => ({
        ...prev,
        status: 'error',
        lastError: error
      }));
      setError('WebSocket connection error');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionDetails(prev => ({
        ...prev,
        status: 'disconnected',
        reconnectAttempts: prev.reconnectAttempts + 1
      }));

      // Exponential backoff for reconnection
      const delay = Math.min(baseReconnectDelay * Math.pow(2, connectionDetails.reconnectAttempts), maxReconnectDelay);
      setTimeout(() => {
        if (connectionDetails.reconnectAttempts < maxReconnectAttempts) {
          console.log(`Attempting to reconnect WebSocket in ${delay}ms...`);
          connectWebSocket();
        } else {
          setError('Maximum reconnection attempts reached');
        }
      }, delay);
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      if (latencyTimeoutRef.current) {
        clearTimeout(latencyTimeoutRef.current);
      }
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current);
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

  const getRegimeColor = (regime) => {
    switch(regime) {
      case 'TRENDING':
        return 'success';
      case 'RANGING':
        return 'info';
      case 'VOLATILE':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getTimeframeColor = (strength) => {
    if (strength >= 0.8) return 'success';
    if (strength >= 0.6) return 'info';
    if (strength >= 0.4) return 'warning';
    return 'error';
  };

  const DataFreshnessPanel = ({ signal }) => {
    if (!signal?.data_freshness) return null;
    
    const getFreshnessColor = (age, maxAge) => {
      const ratio = age / maxAge;
      if (ratio < 0.5) return 'success';
      if (ratio < 0.8) return 'warning';
      return 'error';
    };
    
    return (
      <Card>
        <CardHeader title="Data Freshness" />
        <CardContent>
          <Grid container spacing={2}>
            {Object.entries(signal.data_freshness).map(([type, age]) => (
              <Grid item xs={6} key={type}>
                <Box display="flex" alignItems="center">
                  <Typography variant="body2" style={{ marginRight: 8 }}>
                    {type}:
                  </Typography>
                  <Chip
                    label={`${age.toFixed(1)}s`}
                    color={getFreshnessColor(age, signal.max_allowed_freshness[type])}
                    size="small"
                  />
                </Box>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>
    );
  };

  const DebugPanel = ({ rejectionStats }) => {
    if (!rejectionStats) return null;
    
    return (
      <Card>
        <CardHeader title="Signal Debug Info" />
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="h6">Rejection Reasons</Typography>
              <List dense>
                {Object.entries(rejectionStats.reasons || {}).map(([reason, count]) => (
                  <ListItem key={reason}>
                    <ListItemText
                      primary={reason}
                      secondary={`Count: ${count}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Typography variant="h6">By Market Regime</Typography>
              <List dense>
                {Object.entries(rejectionStats.by_regime || {}).map(([regime, stats]) => (
                  <ListItem key={regime}>
                    <ListItemText
                      primary={regime}
                      secondary={`Rejected: ${stats.rejected} / Total: ${stats.total}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Typography variant="h6">By Confidence</Typography>
              <List dense>
                {Object.entries(rejectionStats.by_confidence || {}).map(([level, stats]) => (
                  <ListItem key={level}>
                    <ListItemText
                      primary={level}
                      secondary={`Rejected: ${stats.rejected} / Total: ${stats.total}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };

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
                    <Box display="flex" gap={1}>
                      <Chip
                        label={signal.signal_type}
                        color={signal.signal_type === 'LONG' ? 'success' : 'error'}
                        size="small"
                      />
                      <Chip
                        label={signal.regime}
                        color={getRegimeColor(signal.regime)}
                        size="small"
                      />
                    </Box>
                  </Box>

                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Strategy
                      </Typography>
                      <Typography variant="body1">
                        {signal.strategy || 'Unknown'}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Confidence
                      </Typography>
                      <Typography variant="body1" color={signal.confidence >= 0.7 ? 'success.main' : 'warning.main'}>
                        {((signal.confidence || 0) * 100).toFixed(1)}%
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography color="textSecondary" variant="body2">
                        Price
                      </Typography>
                      <Typography variant="body1">
                        ${(signal.price || 0).toFixed(2)}
                      </Typography>
                    </Grid>

                    {/* Multi-timeframe Alignment */}
                    <Grid item xs={12}>
                      <Divider sx={{ my: 1 }} />
                      <Typography color="textSecondary" variant="body2" gutterBottom>
                        Timeframe Alignment
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {signal.mtf_alignment?.details && Object.entries(signal.mtf_alignment.details).map(([tf, data]) => (
                          <Chip
                            key={tf}
                            label={`${tf}: ${data.direction}`}
                            color={getTimeframeColor(data.strength)}
                            size="small"
                          />
                        ))}
                      </Box>
                    </Grid>

                    {/* Market Regime Details */}
                    <Grid item xs={12}>
                      <Divider sx={{ my: 1 }} />
                      <Typography color="textSecondary" variant="body2" gutterBottom>
                        Market Regime Details
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {signal.regime === 'TRENDING' && (
                          <>
                            <Chip
                              label={`ADX: ${signal.indicators?.adx?.value?.toFixed(1) || 'N/A'}`}
                              color="success"
                              size="small"
                            />
                            <Chip
                              label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                              color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                              size="small"
                            />
                          </>
                        )}
                        {signal.regime === 'RANGING' && (
                          <>
                            <Chip
                              label={`BB Width: ${signal.indicators?.bollinger_bands?.width?.toFixed(3) || 'N/A'}`}
                              color="info"
                              size="small"
                            />
                            <Chip
                              label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                              color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                              size="small"
                            />
                          </>
                        )}
                        {signal.regime === 'VOLATILE' && (
                          <>
                            <Chip
                              label={`ATR: ${signal.indicators?.atr?.toFixed(2) || 'N/A'}`}
                              color="warning"
                              size="small"
                            />
                            <Chip
                              label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                              color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                              size="small"
                            />
                          </>
                        )}
                        {signal.is_transitioning && (
                          <Chip
                            label="Regime Transition"
                            color="warning"
                            size="small"
                          />
                        )}
                      </Box>
                      {signal.regime_scores && (
                        <Box mt={1}>
                          <Typography variant="caption" color="textSecondary">
                            Regime Scores: {Object.entries(signal.regime_scores)
                              .map(([regime, score]) => `${regime}: ${(score * 100).toFixed(0)}%`)
                              .join(' | ')}
                          </Typography>
                        </Box>
                      )}
                    </Grid>

                    {/* Signal Reasons */}
                    {signal.reasons && signal.reasons.length > 0 && (
                      <Grid item xs={12}>
                        <Divider sx={{ my: 1 }} />
                        <Typography color="textSecondary" variant="body2" gutterBottom>
                          Signal Reasons
                        </Typography>
                        <Box display="flex" gap={1} flexWrap="wrap">
                          {signal.reasons.map((reason, index) => (
                            <Chip
                              key={index}
                              label={reason}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                        </Box>
                      </Grid>
                    )}

                    {/* Time */}
                    <Grid item xs={12}>
                      <Typography color="textSecondary" variant="body2" align="right">
                        {new Date(signal.timestamp).toLocaleTimeString()}
                      </Typography>
                    </Grid>
                  </Grid>

                  <Grid item xs={12}>
                    <DataFreshnessPanel signal={signal} />
                  </Grid>

                  <Grid item xs={12}>
                    <DebugPanel rejectionStats={signal.rejection_stats} />
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