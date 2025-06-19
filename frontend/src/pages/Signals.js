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
  Badge,
  Switch,
  FormControlLabel,
  useTheme,
  useMediaQuery
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import axios from 'axios';
import config from '../config';
import SignalChart from '../components/SignalChart';
import DataFreshnessPanel from '../components/DataFreshnessPanel';

const Signals = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const [autoTradingEnabled, setAutoTradingEnabled] = useState(false);
  const [scanProgress, setScanProgress] = useState(null);
  const [scanStatus, setScanStatus] = useState('idle');
  const [tradingMode, setTradingMode] = useState('stable');
  const [modeDescriptions, setModeDescriptions] = useState({});
  const maxRetries = 3;

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
      // Only show loading state if we have no signals yet (initial load)
      if (signals.length === 0) {
        setLoading(true);
      }
      
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.SIGNALS}`, {
        timeout: 10000, // Increased timeout for background processing
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });

      if (response.data) {
        const data = response.data;
        
        // Parse the correct response format - API returns { status, data: [...] }
        const newSignals = Array.isArray(data.data) ? data.data.map(signal => ({
          symbol: signal.symbol,
          signal_type: signal.direction || 'LONG',
          entry_price: signal.entry_price || signal.entry,
          stop_loss: signal.stop_loss,
          take_profit: signal.take_profit,
          confidence: signal.confidence || signal.confidence_score,
          strategy: signal.strategy || signal.strategy_type,
          timestamp: new Date((signal.timestamp || Date.now())).toISOString(),
          regime: signal.market_regime || signal.regime || 'TRENDING',
          price: signal.entry_price || signal.entry,
          volume: signal.volume_24h || signal.volume,
          volatility: signal.volatility,
          spread: signal.spread,
          score: signal.score,
          
          // Institutional-grade fields
          risk_reward: signal.risk_reward || 1.5,
          recommended_leverage: signal.recommended_leverage || signal.leverage || 1.0,
          position_size: signal.position_size || 0,
          notional_value: signal.notional_value || 0,
          expected_profit: signal.expected_profit || 0,
          expected_return: signal.expected_return || 0,
          
          // $100 investment specific fields
          investment_amount_100: signal.investment_amount_100 || 100,
          position_size_100: signal.position_size_100 || 0,
          max_position_with_leverage_100: signal.max_position_with_leverage_100 || 0,
          expected_profit_100: signal.expected_profit_100 || 0,
          expected_return_100: signal.expected_return_100 || 0,
          
          indicators: {
            macd: { value: 0, signal: 0 },
            rsi: 50,
            bb: { upper: 0, middle: 0, lower: 0 }
          },
          is_stable_signal: signal.is_stable_signal || false,
          invalidation_reason: signal.invalidation_reason || null,
          signal_timestamp: signal.signal_timestamp || null
        })) : [];
        
        // Only update state if data has actually changed to prevent unnecessary re-renders
        const newSignalsJson = JSON.stringify(newSignals);
        const currentSignalsJson = JSON.stringify(signals);
        
        if (newSignalsJson !== currentSignalsJson) {
          setSignals(newSignals);
        }
        
        // Handle scan status properly
        const currentStatus = data.status || 'complete';
        setScanStatus(currentStatus);
        
        // Create scan progress based on status
        const progressData = currentStatus === 'partial' || currentStatus === 'scanning' ? {
          in_progress: true,
          opportunities_found: newSignals.length
        } : null;
        
        // Only update scan progress if it has changed
        if (JSON.stringify(progressData) !== JSON.stringify(scanProgress)) {
          setScanProgress(progressData);
        }
        
        setLastUpdated(new Date());
        setError(null);
        setRetryCount(0);
      }
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

  const executeManualTrade = async (signal) => {
    try {
      const tradeRequest = {
        symbol: signal.symbol,
        signal_type: signal.signal_type,
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit,
        confidence: signal.confidence,
        strategy: signal.strategy || 'manual'
      };

      const response = await axios.post(
        `${config.API_BASE_URL}${config.ENDPOINTS.EXECUTE_MANUAL_TRADE}`,
        tradeRequest,
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.status === 'success') {
        setError(null);
        // Show success message
        setError(`✅ ${response.data.message}`);
        setTimeout(() => setError(null), 5000);
      }
      } catch (err) {
      console.error('Error executing manual trade:', err);
      setError(`❌ Failed to execute trade: ${err.response?.data?.detail || err.message}`);
    }
  };

  const toggleAutoTrading = async () => {
    try {
      const newState = !autoTradingEnabled;
      setAutoTradingEnabled(newState);
      
      // Show status message
      setError(`🤖 Auto-trading ${newState ? 'ENABLED' : 'DISABLED'} - ${newState ? 'Bot will execute trades automatically' : 'Manual trading only'}`);
      setTimeout(() => setError(null), 3000);
      
      // TODO: In the future, this would call an API endpoint to enable/disable auto-trading
      // await axios.post(`${config.API_BASE_URL}/api/v1/trading/auto_trading`, { enabled: newState });
      
      } catch (err) {
      console.error('Error toggling auto-trading:', err);
      setError('❌ Failed to toggle auto-trading');
      setAutoTradingEnabled(!autoTradingEnabled); // Revert on error
    }
  };

  const fetchTradingMode = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}/api/v1/trading/mode`);
      if (response.data.status === 'success') {
        setTradingMode(response.data.trading_mode);
        setModeDescriptions(response.data.mode_descriptions);
      }
    } catch (err) {
      console.error('Error fetching trading mode:', err);
    }
  };

  const changeTradingMode = async (newMode) => {
    try {
      setError(`🔄 Switching to ${newMode} mode...`);
      
      const response = await axios.post(`${config.API_BASE_URL}/api/v1/trading/mode/${newMode}`);
      
      if (response.data.status === 'success') {
        setTradingMode(newMode);
        setError(`✅ Switched to ${newMode} mode - ${response.data.message}`);
        setTimeout(() => setError(null), 5000);
        
        // Refresh signals after mode change
        setTimeout(() => {
          fetchSignals();
        }, 1000);
      }
    } catch (err) {
      console.error('Error changing trading mode:', err);
      setError(`❌ Failed to change trading mode: ${err.response?.data?.message || err.message}`);
    }
  };

  useEffect(() => {
    fetchSignals();
    fetchTradingMode(); // Fetch current trading mode
    
    // Single interval with dynamic timing
    let interval;
    
    const setupInterval = () => {
      const getPollingInterval = () => {
        if (scanProgress && scanProgress.in_progress) {
          return 3000; // 3 seconds during active scan
        }
        return 10000; // 10 seconds normally
      };
      
      interval = setInterval(fetchSignals, getPollingInterval());
    };
    
    setupInterval();
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [retryCount]); // Removed scanProgress dependency to prevent constant re-renders

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

  // Smart price formatting function - shows appropriate precision based on price value
  const formatPrice = (price) => {
    if (!price || isNaN(price)) return 'N/A';
    
    if (price >= 1000) {
      return price.toFixed(2);  // $1000+ -> 2 decimals (e.g., $104,799.85)
    } else if (price >= 100) {
      return price.toFixed(3);  // $100-999 -> 3 decimals (e.g., $458.110)
    } else if (price >= 10) {
      return price.toFixed(4);  // $10-99 -> 4 decimals (e.g., $85.1300)
    } else if (price >= 1) {
      return price.toFixed(5);  // $1-9 -> 5 decimals (e.g., $2.16420)
    } else if (price >= 0.1) {
      return price.toFixed(6);  // $0.1-0.99 -> 6 decimals (e.g., $0.274140)
    } else {
      return price.toFixed(8);  // <$0.1 -> 8 decimals (e.g., $0.00012345)
    }
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
      regime,
      strategy,
      timestamp
    } = signal;

    return (
      <Card 
        key={symbol} 
        sx={{ 
          height: '100%',
          maxWidth: '100%',
          overflow: 'hidden'
        }}
      >
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1} sx={{ flexWrap: 'wrap' }}>
              <Typography 
                variant="h6" 
                component="span"
                sx={{ 
                  fontSize: { xs: '1rem', sm: '1.25rem' },
                  fontWeight: 'bold'
                }}
              >
                {symbol}
              </Typography>
              <Chip
                label={signal_type}
                color={signal_type === 'LONG' ? 'success' : 'error'}
                size="small"
                sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
              />
              {signal.is_stable_signal && (
                <Chip
                  label="STABLE"
                  color="info"
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: { xs: '0.6rem', sm: '0.7rem' } }}
                />
              )}
              {signal.invalidation_reason && (
                <Chip
                  label="INVALIDATED"
                  color="warning"
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: { xs: '0.6rem', sm: '0.7rem' } }}
                />
              )}
            </Box>
          }
          subheader={
            <Box>
              <Typography 
                variant="body2" 
                color="text.secondary"
                sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' } }}
              >
                {strategy} • {regime}
              </Typography>
              {signal.invalidation_reason && (
                <Typography 
                  variant="caption" 
                  color="warning.main" 
                  sx={{ 
                    fontStyle: 'italic',
                    fontSize: { xs: '0.65rem', sm: '0.75rem' }
                  }}
                >
                  ⚠️ {signal.invalidation_reason}
                </Typography>
              )}
              {signal.signal_timestamp && (
                <Typography 
                  variant="caption" 
                  color="text.secondary" 
                  sx={{ 
                    display: 'block',
                    fontSize: { xs: '0.65rem', sm: '0.75rem' }
                  }}
                >
                  Signal age: {Math.round((Date.now() - signal.signal_timestamp) / 1000 / 60)}m
                </Typography>
              )}
            </Box>
          }
          sx={{ 
            pb: { xs: 1, sm: 2 },
            '& .MuiCardHeader-content': {
              overflow: 'hidden'
            }
          }}
        />
        <CardContent sx={{ pt: 0, px: { xs: 1.5, sm: 2 }, pb: { xs: 1.5, sm: 2 } }}>
          <Grid container spacing={{ xs: 1, sm: 2 }} mb={{ xs: 1.5, sm: 2 }}>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Entry Price
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }
                  }}
                >
                  {formatPrice(entry_price)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Stop Loss
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }
                  }}
                >
                  {formatPrice(stop_loss)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Take Profit
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }
                  }}
                >
                  {formatPrice(take_profit)}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Grid container spacing={{ xs: 1, sm: 2 }} mb={{ xs: 1.5, sm: 2 }}>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Confidence
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' },
                    color: confidence > 0.7 ? 'success.main' : confidence > 0.5 ? 'warning.main' : 'error.main'
                  }}
                >
                  {(confidence * 100)?.toFixed(0) || 'N/A'}{confidence > 0.7 ? '% 🏛️' : confidence > 0.5 ? '% ⚠️' : '% ❌'} 
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Risk/Reward
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' },
                    color: signal.risk_reward > 2 ? 'success.main' : 'inherit'
                  }}
                >
                  {signal.risk_reward?.toFixed(1) || 'N/A'}:1
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Leverage
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }
                  }}
                >
                  {signal.recommended_leverage?.toFixed(1) || '1.0'}x
                </Typography>
              </Box>
            </Grid>
          </Grid>

          {/* $100 Investment Section - Highlighted */}
          <Box 
            sx={{ 
              backgroundColor: 'primary.main', 
              color: 'primary.contrastText', 
              p: { xs: 1.5, sm: 2.5 }, 
              borderRadius: 2, 
              mb: { xs: 1.5, sm: 2 },
              border: '1px solid',
              borderColor: 'primary.dark',
              boxShadow: 2
            }}
          >
            <Typography 
              variant="h6" 
              sx={{ 
                mb: { xs: 1.5, sm: 2 }, 
                textAlign: 'center',
                fontWeight: 'bold',
                fontSize: { xs: '0.9rem', sm: '1.1rem' }
              }}
            >
              💰 $100 Investment with {signal.recommended_leverage?.toFixed(1) || '1.0'}x Leverage
            </Typography>
            <Grid container spacing={{ xs: 1, sm: 2 }} sx={{ textAlign: 'center' }}>
              <Grid item xs={4}>
                <Box sx={{ 
                  minHeight: { xs: '50px', sm: '60px' }, 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'center' 
                }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: { xs: '0.6rem', sm: '0.75rem' },
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Trading Power
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      fontWeight: 'bold',
                      fontSize: { xs: '1rem', sm: '1.25rem' },
                      lineHeight: 1.2
                    }}
                  >
                    {formatPrice(signal.max_position_with_leverage_100)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ 
                  minHeight: { xs: '50px', sm: '60px' }, 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'center' 
                }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: { xs: '0.6rem', sm: '0.75rem' },
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Expected Profit
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      color: 'success.light',
                      fontWeight: 'bold',
                      fontSize: { xs: '1rem', sm: '1.25rem' },
                      lineHeight: 1.2
                    }}
                  >
                    {formatPrice(signal.expected_profit_100)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ 
                  minHeight: { xs: '50px', sm: '60px' }, 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'center' 
                }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      opacity: 0.9, 
                      fontSize: { xs: '0.6rem', sm: '0.75rem' },
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      mb: 0.5
                    }}
                  >
                    Return %
                  </Typography>
                  <Typography 
                    variant="h5" 
                    sx={{ 
                      color: 'success.light',
                      fontWeight: 'bold',
                      fontSize: { xs: '1rem', sm: '1.25rem' },
                      lineHeight: 1.2
                    }}
                  >
                    {signal.expected_return_100 ? (signal.expected_return_100 * 100).toFixed(1) + '%' : 'N/A'}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>

          <Grid container spacing={{ xs: 1, sm: 2 }} mb={{ xs: 1.5, sm: 2 }}>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Position Size
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }
                  }}
                >
                  {formatPrice(signal.notional_value)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Expected Profit
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }, 
                    color: 'success.main' 
                  }}
                >
                  {formatPrice(signal.expected_profit)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '40px', sm: '50px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.6rem', sm: '0.75rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Expected Return
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 'bold', 
                    fontSize: { xs: '0.8rem', sm: '1rem' }, 
                    color: 'success.main' 
                  }}
                >
                  {signal.expected_return ? (signal.expected_return * 100).toFixed(1) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Grid container spacing={{ xs: 1, sm: 2 }} mb={{ xs: 1.5, sm: 2 }}>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '35px', sm: '45px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.55rem', sm: '0.7rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Volume
                </Typography>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    fontWeight: 'medium', 
                    fontSize: { xs: '0.75rem', sm: '0.9rem' }
                  }}
                >
                  {signal.volume ? (signal.volume / 1000000).toFixed(2) + 'M' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '35px', sm: '45px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.55rem', sm: '0.7rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Volatility
                </Typography>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    fontWeight: 'medium', 
                    fontSize: { xs: '0.75rem', sm: '0.9rem' }
                  }}
                >
                  {signal.volatility ? (signal.volatility * 100).toFixed(3) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={4}>
              <Box sx={{ 
                textAlign: 'center', 
                minHeight: { xs: '35px', sm: '45px' }, 
                display: 'flex', 
                flexDirection: 'column', 
                justifyContent: 'center' 
              }}>
                <Typography 
                  color="textSecondary" 
                  variant="body2" 
                  sx={{ 
                    fontSize: { xs: '0.55rem', sm: '0.7rem' }, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.5px', 
                    mb: 0.5 
                  }}
                >
                  Spread
                </Typography>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    fontWeight: 'medium', 
                    fontSize: { xs: '0.75rem', sm: '0.9rem' }
                  }}
                >
                  {signal.spread ? (signal.spread * 100).toFixed(3) + '%' : 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: { xs: 1.5, sm: 2 } }} />
          
          <Box 
            display="flex" 
            justifyContent="space-between" 
            alignItems="center"
            sx={{ 
              flexDirection: { xs: 'column', sm: 'row' },
              gap: { xs: 1.5, sm: 0 }
            }}
          >
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ 
                fontSize: { xs: '0.65rem', sm: '0.75rem' },
                textAlign: { xs: 'center', sm: 'left' }
              }}
            >
              {timestamp ? new Date(timestamp).toLocaleString() : 'No timestamp'}
            </Typography>
            <Button
              variant="contained"
              color={signal_type === 'LONG' ? 'success' : 'error'}
              size={isMobile ? 'small' : 'medium'}
              startIcon={signal_type === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />}
              onClick={() => executeManualTrade(signal)}
              sx={{ 
                fontWeight: 'bold',
                px: { xs: 2, sm: 3 },
                py: { xs: 0.5, sm: 1 },
                borderRadius: 2,
                boxShadow: 2,
                fontSize: { xs: '0.75rem', sm: '0.875rem' },
                '&:hover': {
                  boxShadow: 3
                }
              }}
            >
              Execute {signal_type} Trade
            </Button>
          </Box>
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
    <Box sx={{ 
      p: { xs: 1, sm: 2, md: 3 },
      maxWidth: '100vw',
      overflow: 'hidden'
    }}>
      <Box 
        display="flex" 
        justifyContent="space-between" 
        alignItems="center" 
        mb={{ xs: 2, sm: 3 }}
        sx={{
          flexDirection: { xs: 'column', sm: 'row' },
          gap: { xs: 1, sm: 0 }
        }}
      >
        <Typography 
          variant="h4" 
          sx={{ 
            fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' },
            mb: { xs: 1, sm: 0 }
          }}
        >
          Trading Signals
        </Typography>
        <Box 
          display="flex" 
          alignItems="center" 
          gap={{ xs: 1, sm: 2 }}
          sx={{
            flexDirection: { xs: 'column', sm: 'row' },
            width: { xs: '100%', sm: 'auto' }
          }}
        >
          {/* Trading Mode Selector */}
          <FormControl 
            size="small" 
            sx={{ 
              minWidth: { xs: '100%', sm: 140 },
              maxWidth: { xs: '100%', sm: 200 }
            }}
          >
            <InputLabel sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
              Trading Mode
            </InputLabel>
            <Select
              value={tradingMode}
              label="Trading Mode"
              onChange={(e) => changeTradingMode(e.target.value)}
              disabled={loading}
              sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
            >
              <MenuItem value="stable">
                <Box>
                  <Typography variant="body2" fontWeight="bold" sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                    Stable
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                    Conservative ATR-based
                  </Typography>
                </Box>
              </MenuItem>
              <MenuItem value="swing_trading">
                <Box>
                  <Typography variant="body2" fontWeight="bold" sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                    Swing Trading
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                    Multi-strategy + Structure
                  </Typography>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>
          
          <FormControlLabel
            control={
              <Switch
                checked={autoTradingEnabled}
                onChange={toggleAutoTrading}
                color="success"
                size={isMobile ? 'small' : 'medium'}
              />
            }
            label={
              <Box display="flex" alignItems="center" gap={1}>
                <Typography variant="body2" sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                  Auto-Trading
                </Typography>
                <Chip
                  label={autoTradingEnabled ? 'ON' : 'OFF'}
                  color={autoTradingEnabled ? 'success' : 'default'}
                  size="small"
                  sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
                />
            </Box>
            }
            sx={{ 
              m: 0,
              width: { xs: '100%', sm: 'auto' },
              justifyContent: { xs: 'center', sm: 'flex-start' }
            }}
          />
          
          <Box 
            display="flex" 
            alignItems="center" 
            gap={1}
            sx={{ 
              width: { xs: '100%', sm: 'auto' },
              justifyContent: { xs: 'center', sm: 'flex-start' }
            }}
          >
            <Chip
              label={`Status: ${loading && signals.length === 0 ? 'LOADING' : signals.length > 0 ? 'ACTIVE' : 'NO DATA'}`}
              color={loading && signals.length === 0 ? 'warning' : signals.length > 0 ? 'success' : 'default'}
              size="small"
              sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
            />
            <Tooltip title="Refresh signals">
              <IconButton 
                onClick={fetchSignals} 
                disabled={loading}
                size="small"
                sx={{ p: { xs: 0.5, sm: 1 } }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Box>

      {/* Trading Mode Info */}
      <Alert 
        severity={tradingMode === 'swing_trading' ? 'warning' : 'info'} 
        sx={{ 
          mb: 2,
          fontSize: { xs: '0.75rem', sm: '0.875rem' },
          '& .MuiAlert-message': {
            fontSize: { xs: '0.75rem', sm: '0.875rem' }
          }
        }}
        icon={tradingMode === 'swing_trading' ? '🎯' : '🛡️'}
      >
        <strong>{tradingMode === 'swing_trading' ? 'SWING TRADING MODE' : 'STABLE MODE'}</strong> - {
          tradingMode === 'swing_trading' 
            ? 'Advanced multi-strategy voting with structure-based TP/SL targeting 5-10% moves. Requires 2+ strategy consensus.'
            : 'Conservative signals with ATR-based TP/SL and signal persistence. Optimized for stability.'
        }
      </Alert>

      {/* Auto-trading status alert */}
      {autoTradingEnabled && (
        <Alert 
          severity="info" 
          sx={{ 
            mb: 2,
            fontSize: { xs: '0.75rem', sm: '0.875rem' },
            '& .MuiAlert-message': {
              fontSize: { xs: '0.75rem', sm: '0.875rem' }
            }
          }}
        >
          🤖 <strong>Auto-Trading is ENABLED</strong> - The bot will automatically execute trades based on signals. 
          You can still manually execute individual trades using the buttons below.
        </Alert>
      )}

      {error && (
        <Snackbar 
          open={!!error} 
          autoHideDuration={error.includes('🔄') || error.includes('⏳') ? null : 6000}
          onClose={() => setError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          sx={{
            '& .MuiSnackbarContent-root': {
              maxWidth: { xs: '90vw', sm: 'none' }
            }
          }}
        >
          <Alert 
            severity={
              error.includes('✅') ? 'success' : 
              error.includes('🔄') || error.includes('⏳') ? 'info' : 
              'error'
            } 
            onClose={() => setError(null)}
            action={
              !error.includes('✅') && !error.includes('🔄') && !error.includes('⏳') && (
              <Button 
                color="inherit" 
                size="small" 
                onClick={fetchSignals}
                sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' } }}
              >
                Retry
              </Button>
              )
            }
            sx={{
              fontSize: { xs: '0.75rem', sm: '0.875rem' },
              '& .MuiAlert-message': {
                fontSize: { xs: '0.75rem', sm: '0.875rem' }
              }
            }}
          >
            {error}
          </Alert>
        </Snackbar>
      )}

      <Box mb={{ xs: 2, sm: 3 }}>
        <Grid container spacing={{ xs: 1, sm: 2 }}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Filter signals"
              variant="outlined"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search by symbol or strategy..."
              size="small"
              sx={{
                '& .MuiInputBase-input': {
                  fontSize: { xs: '0.8rem', sm: '0.875rem' }
                },
                '& .MuiInputLabel-root': {
                  fontSize: { xs: '0.8rem', sm: '0.875rem' }
                }
              }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
                Sort by
              </InputLabel>
              <Select
                value={sortBy}
                label="Sort by"
                onChange={(e) => handleSort(e.target.value)}
                sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
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
        <Typography 
          variant="caption" 
          color="textSecondary" 
          sx={{ 
            mb: 2, 
            display: 'block',
            fontSize: { xs: '0.7rem', sm: '0.75rem' }
          }}
        >
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      )}

      <Box mb={{ xs: 2, sm: 3 }}>
        <DataFreshnessPanel 
          lastUpdated={lastUpdated}
          signalsCount={signals.length}
          onRefresh={fetchSignals}
        />
      </Box>

      {/* Scan Progress Indicator */}
      {scanProgress && scanProgress.in_progress && (
        <Box mb={{ xs: 2, sm: 3 }}>
          <Paper sx={{ 
            p: { xs: 1.5, sm: 2 }, 
            bgcolor: 'info.light', 
            borderLeft: '4px solid', 
            borderColor: 'info.main' 
          }}>
            <Grid container spacing={{ xs: 1, sm: 2 }} alignItems="center">
              <Grid item>
                <CircularProgress size={{ xs: 20, sm: 24 }} />
              </Grid>
              <Grid item xs>
                <Typography 
                  variant="body1" 
                  fontWeight="bold"
                  sx={{ fontSize: { xs: '0.8rem', sm: '1rem' } }}
                >
                  Scan in Progress
                </Typography>
                <Typography 
                  variant="body2" 
                  color="text.secondary"
                  sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' } }}
                >
                  {scanProgress.opportunities_found > 0 
                    ? `Found ${scanProgress.opportunities_found} opportunities so far...`
                    : 'Scanning markets for trading opportunities...'
                  }
                </Typography>
              </Grid>
              <Grid item>
                <Chip 
                  label={scanStatus === 'scanning' ? 'Starting...' : 'Processing'} 
                  color="info" 
                  size="small"
                  sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}
                />
              </Grid>
            </Grid>
          </Paper>
        </Box>
      )}

      <Grid container spacing={{ xs: 2, sm: 3 }}>
          <Grid item xs={12}>
          <Paper sx={{ p: { xs: 1.5, sm: 2 } }}>
            <Typography 
              variant="h6" 
              gutterBottom
              sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
            >
              Trading Opportunities ({signals.length} found)
            </Typography>
            {signals.length === 0 ? (
              <Typography 
                color="textSecondary"
                sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
              >
                No trading opportunities available
              </Typography>
            ) : (
              <Grid container spacing={{ xs: 1.5, sm: 2 }}>
                {filteredAndSortedSignals.map((signal, index) => (
                  <Grid item xs={12} md={6} key={`${signal.symbol}-${index}`}>
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