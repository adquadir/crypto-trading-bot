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
  ListItemText,
  Badge
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import axios from 'axios';
import config from '../config';
import { useWebSocket } from '../contexts/WebSocketContext';
import SignalChart from '../components/SignalChart';
import DataFreshnessPanel from '../components/DataFreshnessPanel';

const Signals = () => {
  const { isConnected, lastMessage } = useWebSocket();
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

  useEffect(() => {
    if (lastMessage) {
      try {
        if (lastMessage.type === 'signal') {
          setSignals(prevSignals => {
            const newSignals = [...prevSignals, lastMessage.data];
            // Keep only the last 100 signals
            return newSignals.slice(-100);
          });
        }
      } catch (err) {
        console.error('Error processing WebSocket message:', err);
        setError('Error processing signal data');
      }
    }
  }, [lastMessage]);

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

  const SignalCard = ({ signal }) => {
    const {
      symbol,
      signal_type,
      entry_price,
      stop_loss,
      take_profit,
      confidence,
      mtf_alignment,
      regime
    } = signal;

    return (
      <Card className="mb-4">
        <Card.Body>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="mb-0">{symbol}</h5>
            <Badge bg={signal_type === 'LONG' ? 'success' : 'danger'}>
              {signal_type}
            </Badge>
          </div>
          
          <div className="row mb-3">
            <div className="col-md-4">
              <div className="text-muted small">Entry Price</div>
              <div>${entry_price.toFixed(2)}</div>
            </div>
            <div className="col-md-4">
              <div className="text-muted small">Stop Loss</div>
              <div>${stop_loss.toFixed(2)}</div>
            </div>
            <div className="col-md-4">
              <div className="text-muted small">Take Profit</div>
              <div>${take_profit.toFixed(2)}</div>
            </div>
          </div>

          <div className="row mb-3">
            <div className="col-md-4">
              <div className="text-muted small">Confidence</div>
              <div>{confidence.toFixed(2)}</div>
            </div>
            <div className="col-md-4">
              <div className="text-muted small">Regime</div>
              <div className="text-capitalize">{regime}</div>
            </div>
            <div className="col-md-4">
              <div className="text-muted small">MTF Alignment</div>
              <div>{mtf_alignment?.strength.toFixed(2) || 'N/A'}</div>
            </div>
          </div>

          {mtf_alignment && (
            <div className="mt-3">
              <h6 className="mb-2">Timeframe Alignments</h6>
              <div className="row">
                {mtf_alignment.timeframes.map(tf => (
                  <div key={tf} className="col-md-4 mb-2">
                    <div className="text-muted small">{tf}</div>
                    <div>
                      {Object.entries(mtf_alignment.alignments[tf]).map(([type, aligned]) => (
                        <Badge
                          key={type}
                          bg={aligned ? 'success' : 'secondary'}
                          className="me-1"
                        >
                          {type}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card.Body>
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
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Latest Signals
            </Typography>
            {signals.length > 0 && (
              <DataFreshnessPanel signal={signals[signals.length - 1]} />
            )}
            {signals.length === 0 ? (
              <Typography color="textSecondary">
                No signals available
              </Typography>
            ) : (
              <Grid container spacing={2}>
                {signals.map((signal, index) => (
                  <Grid item xs={12} md={6} key={index}>
                    <SignalCard signal={signal} />
                  </Grid>
                ))}
              </Grid>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Signals; 