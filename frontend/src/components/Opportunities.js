import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Grid,
  TextField,
  Alert,
  Divider,
  Stack,
  FormControl,
  FormControlLabel,
  Switch
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useMediaQuery } from '@mui/system';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  MonetizationOn as ProfitIcon,
  Speed as SpeedIcon,
  TrendingFlat as PrecisionIcon,
  AccountBalance as LeverageIcon,
  TouchApp as TouchIcon,
  Assessment as AssessmentIcon
} from '@mui/icons-material';
import axios from 'axios';
import config from '../config';

// 3% Precision Trading Calculator
const calculateProfitScenarios = (entry, takeProfit, stopLoss, direction) => {
  const priceMove = Math.abs(takeProfit - entry);
  const risk = Math.abs(entry - stopLoss);
  const movePct = (priceMove / entry) * 100;
  
  const scenarios = [
    { capital: 100, leverage: 5 },
    { capital: 500, leverage: 10 },
    { capital: 1000, leverage: 10 },
    { capital: 2000, leverage: 15 },
  ];
  
  return scenarios.map(scenario => {
    const grossProfit = scenario.capital * (movePct / 100) * scenario.leverage;
    const riskAmount = scenario.capital * (risk / entry) * scenario.leverage;
    return {
      ...scenario,
      movePct: movePct,
      grossProfit: grossProfit,
      riskAmount: riskAmount,
      riskReward: grossProfit / riskAmount
    };
  });
};

// Signal Quality Scoring for 3% Precision
const calculatePrecisionScore = (signal) => {
  let score = 0;
  const entry = signal.entry || signal.entry_price || 0;
  const tp = signal.take_profit || signal.takeProfit || 0;
  const sl = signal.stop_loss || signal.stopLoss || 0;
  
  if (!entry || !tp || !sl) return 0;
  
  const movePct = Math.abs((tp - entry) / entry) * 100;
  const confidence = signal.confidence || signal.confidence_score || 0;
  
  // Perfect 3% move gets max points
  if (movePct >= 2.5 && movePct <= 3.5) score += 30;
  else if (movePct >= 2.0 && movePct <= 4.0) score += 20;
  else if (movePct >= 1.5 && movePct <= 5.0) score += 10;
  
  // High confidence gets points
  score += confidence * 30;
  
  // Risk/reward ratio
  const rr = Math.abs(tp - entry) / Math.abs(entry - sl);
  if (rr >= 2.0) score += 20;
  else if (rr >= 1.5) score += 15;
  else if (rr >= 1.0) score += 10;
  
  // Volume and regime bonus
  if (signal.regime === 'TRENDING') score += 10;
  if (signal.volume_ratio && signal.volume_ratio > 1.2) score += 10;
  
  return Math.min(100, score);
};

const ProfitCalculator = ({ signal }) => {
  const [capital, setCapital] = useState(500);
  const [leverage, setLeverage] = useState(10);
  
  if (!signal.entry && !signal.entry_price) return null;
  if (!signal.take_profit && !signal.takeProfit) return null;
  
  const entry = signal.entry || signal.entry_price;
  const tp = signal.take_profit || signal.takeProfit;
  const sl = signal.stop_loss || signal.stopLoss || entry * 0.98; // Default 2% SL
  
  const movePct = Math.abs((tp - entry) / entry) * 100;
  const grossProfit = capital * (movePct / 100) * leverage;
  const risk = Math.abs(entry - sl);
  const riskAmount = capital * (risk / entry) * leverage;
  
  return (
    <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid #e0e0e0' }}>
      <Typography variant="subtitle2" color="primary" gutterBottom>
        🎯 3% Precision Profit Calculator
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <TextField
            label="Capital ($)"
            type="number"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
            size="small"
            fullWidth
          />
        </Grid>
        <Grid item xs={6}>
          <TextField
            label="Leverage"
            type="number"
            value={leverage}
            onChange={(e) => setLeverage(Number(e.target.value))}
            size="small"
            fullWidth
            inputProps={{ min: 1, max: 20 }}
          />
        </Grid>
        <Grid item xs={12}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mt={1}>
            <Typography variant="body2">
              <strong>Move:</strong> {movePct.toFixed(2)}%
            </Typography>
            <Typography variant="body2" color="success.main">
              <strong>Profit:</strong> ${grossProfit.toFixed(2)}
            </Typography>
            <Typography variant="body2" color="error.main">
              <strong>Risk:</strong> ${riskAmount.toFixed(2)}
            </Typography>
            <Typography variant="body2">
              <strong>R:R:</strong> {(grossProfit / riskAmount).toFixed(2)}
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

const PrecisionBadge = ({ signal }) => {
  const score = calculatePrecisionScore(signal);
  const getColor = () => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };
  
  return (
    <Chip
      icon={<PrecisionIcon />}
      label={`${score.toFixed(0)}% Precision`}
      color={getColor()}
      size="small"
      variant="outlined"
    />
  );
};

const CertaintyBadge = ({ signal }) => {
  const certaintyLabel = signal.certainty_label || 'UNKNOWN';
  const certaintyScore = signal.certainty_score || 0;
  const winRate = signal.expected_win_rate || '?';
  
  const getColor = () => {
    switch(certaintyLabel) {
      case 'GUARANTEED': return 'success';
      case 'VERY HIGH': return 'info';
      case 'HIGH': return 'warning';
      case 'MODERATE': return 'secondary';
      case 'LOW': return 'error';
      case 'REJECTED': return 'error';
      default: return 'default';
    }
  };
  
  const getIcon = () => {
    switch(certaintyLabel) {
      case 'GUARANTEED': return '🟢';
      case 'VERY HIGH': return '🔵';
      case 'HIGH': return '🟡';
      case 'MODERATE': return '🟠';
      case 'LOW': return '🔴';
      case 'REJECTED': return '❌';
      default: return '⚪';
    }
  };
  
  return (
    <Box>
      <Chip
        icon={<span>{getIcon()}</span>}
        label={`${certaintyLabel} (${certaintyScore}/100)`}
        color={getColor()}
        size="small"
        variant="filled"
        sx={{ fontWeight: 'bold', mb: 0.5 }}
      />
      <Typography variant="caption" display="block" color="textSecondary">
        Expected: {winRate} win rate
      </Typography>
    </Box>
  );
};

// Mobile-Friendly Signal Card Component
const SignalCard = ({ signal, onDetailsClick }) => {
  const entry = signal.entry || signal.entry_price || 0;
  const tp = signal.take_profit || signal.takeProfit || 0;
  const sl = signal.stop_loss || signal.stopLoss || entry * 0.98;
  const confidence = signal.confidence || signal.confidence_score || 0;
  const movePct = Math.abs((tp - entry) / entry) * 100;
  const riskReward = Math.abs(tp - entry) / Math.abs(entry - sl);
  const profitAt10x = 500 * (movePct / 100) * 10;
  
  const getDirectionColor = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return 'success';
      case 'short':
      case 'sell':
        return 'error';
      default:
        return 'default';
    }
  };

  const getDirectionIcon = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return <TrendingUpIcon />;
      case 'short':
      case 'sell':
        return <TrendingDownIcon />;
      default:
        return null;
    }
  };

  return (
    <Card 
      sx={{ 
        mb: 2, 
        borderRadius: 2, 
        boxShadow: 2,
        '&:hover': { boxShadow: 4 },
        border: '1px solid #e0e0e0'
      }}
    >
      <CardContent sx={{ p: 2 }}>
        {/* Header Row */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="h6" fontWeight="bold" color="primary">
              {signal.symbol}
            </Typography>
            <Chip
              icon={getDirectionIcon(signal.direction)}
              label={signal.direction}
              color={getDirectionColor(signal.direction)}
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
          </Box>
          <IconButton 
            size="small" 
            color="primary"
            onClick={() => onDetailsClick(signal)}
            sx={{ p: 1 }}
          >
            <InfoIcon />
          </IconButton>
        </Box>

        {/* Certainty Badge - Prominent */}
        <Box mb={2}>
          <CertaintyBadge signal={signal} />
        </Box>

        {/* Key Metrics Grid */}
        <Grid container spacing={2} mb={2}>
          <Grid item xs={6}>
            <Box textAlign="center" p={1} bgcolor="background.default" borderRadius={1}>
              <Typography variant="caption" color="textSecondary">Entry Price</Typography>
              <Typography variant="body1" fontWeight="bold">
                ${entry.toFixed(6)}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box textAlign="center" p={1} bgcolor="success.light" borderRadius={1}>
              <Typography variant="caption" color="textSecondary">Take Profit</Typography>
              <Typography variant="body1" fontWeight="bold" color="success.dark">
                ${tp.toFixed(6)}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box textAlign="center" p={1} bgcolor="error.light" borderRadius={1}>
              <Typography variant="caption" color="textSecondary">Stop Loss</Typography>
              <Typography variant="body1" fontWeight="bold" color="error.dark">
                ${sl.toFixed(6)}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box textAlign="center" p={1} bgcolor="warning.light" borderRadius={1}>
              <Typography variant="caption" color="textSecondary">Move %</Typography>
              <Typography variant="body1" fontWeight="bold" color="warning.dark">
                {movePct.toFixed(2)}%
              </Typography>
            </Box>
          </Grid>
        </Grid>

        {/* Performance Metrics */}
        <Stack direction="row" spacing={2} justifyContent="space-between" mb={2}>
          <Box textAlign="center">
            <Typography variant="caption" color="textSecondary">Confidence</Typography>
            <Typography variant="body2" fontWeight="bold">
              {(confidence * 100).toFixed(1)}%
            </Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="caption" color="textSecondary">Risk:Reward</Typography>
            <Typography variant="body2" fontWeight="bold" color={riskReward >= 2 ? 'success.main' : 'text.primary'}>
              {riskReward.toFixed(2)}:1
            </Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="caption" color="textSecondary">Profit @ 10x</Typography>
            <Typography variant="body2" fontWeight="bold" color="success.main">
              ${profitAt10x.toFixed(0)}
            </Typography>
          </Box>
        </Stack>

        {/* Precision Score */}
        <Box display="flex" justifyContent="center">
          <PrecisionBadge signal={signal} />
        </Box>

        {/* Quick Touch Action */}
        <Box mt={2} textAlign="center">
          <Button
            variant="outlined"
            size="small"
            startIcon={<TouchIcon />}
            onClick={() => onDetailsClick(signal)}
            sx={{ minWidth: '120px' }}
          >
            View Details
          </Button>
        </Box>

        {/* Timestamp */}
        {signal.timestamp && (
          <Typography variant="caption" color="textSecondary" display="block" textAlign="center" mt={1}>
            {new Date(signal.timestamp).toLocaleString()}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

const Opportunities = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));
  
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [filters, setFilters] = useState({
    minPrecisionScore: 0,
    maxMove: 10.0,
    minMove: 0.5,
    minConfidence: 0.0,
    searchText: '',
    showOnlyHighCertainty: false
  });

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 15000);
    return () => clearInterval(interval);
  }, []);

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}/api/v1/trading/opportunities`);
      
      if (response.data && response.data.length > 0) {
        setSignals(response.data);
      } else {
        const oppResponse = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITIES}`);
        const opportunitiesData = oppResponse.data.data || {};
        const opportunitiesArray = Array.isArray(opportunitiesData) 
          ? opportunitiesData 
          : Object.values(opportunitiesData);
        setSignals(opportunitiesArray);
      }
      
      setError(null);
    } catch (err) {
      setError('Failed to fetch trading signals');
      console.error('Error fetching signals:', err);
    } finally {
      setLoading(false);
    }
  };

  const getDirectionColor = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return 'success';
      case 'short':
      case 'sell':
        return 'error';
      default:
        return 'default';
    }
  };

  const getDirectionIcon = (direction) => {
    switch(direction?.toLowerCase()) {
      case 'long':
      case 'buy':
        return <TrendingUpIcon />;
      case 'short':
      case 'sell':
        return <TrendingDownIcon />;
      default:
        return null;
    }
  };

  const filteredSignals = signals.filter(signal => {
    const entry = signal.entry || signal.entry_price || 0;
    const tp = signal.take_profit || signal.takeProfit || 0;
    const confidence = signal.confidence || signal.confidence_score || 0;
    
    if (!entry || !tp) return false;
    
    const movePct = Math.abs((tp - entry) / entry) * 100;
    const precisionScore = calculatePrecisionScore(signal);
    const certaintyLabel = signal.certainty_label || 'UNKNOWN';
    
    // High-certainty filter
    if (filters.showOnlyHighCertainty) {
      const isHighCertainty = ['GUARANTEED', 'VERY HIGH', 'HIGH'].includes(certaintyLabel);
      if (!isHighCertainty) return false;
    }
    
    return (
      precisionScore >= filters.minPrecisionScore &&
      movePct >= filters.minMove &&
      movePct <= filters.maxMove &&
      confidence >= filters.minConfidence &&
      (signal.symbol || '').toLowerCase().includes(filters.searchText.toLowerCase())
    );
  }).sort((a, b) => {
    // Sort by certainty score first, then precision score
    const aCertainty = a.certainty_score || 0;
    const bCertainty = b.certainty_score || 0;
    if (aCertainty !== bCertainty) {
      return bCertainty - aCertainty;
    }
    const aPrecision = calculatePrecisionScore(a);
    const bPrecision = calculatePrecisionScore(b);
    return bPrecision - aPrecision;
  });

  const handleDetailsClick = (signal) => {
    setSelectedSignal(signal);
    setDetailsOpen(true);
  };

  const handleCloseDetails = () => {
    setDetailsOpen(false);
    setSelectedSignal(null);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={isMobile ? 40 : 60} />
        {!isMobile && (
          <Typography variant="h6" sx={{ ml: 2 }}>
            Loading opportunities...
          </Typography>
        )}
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      {/* Mobile-Optimized Header with Stats */}
      <Paper 
        sx={{ 
          p: { xs: 2, sm: 3 }, 
          mb: { xs: 2, sm: 3 },
          background: 'linear-gradient(135deg, rgba(144, 202, 249, 0.1) 0%, rgba(244, 143, 177, 0.1) 100%)'
        }}
      >
        <Grid container spacing={{ xs: 2, sm: 3 }} alignItems="center">
          <Grid item xs={12} sm={8}>
            <Typography variant={isMobile ? "h6" : "h5"} fontWeight="bold" gutterBottom>
              🎯 Precision Trading Opportunities
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {filteredSignals.length} active opportunities • Updated every 15 seconds
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Box display="flex" gap={1} flexWrap="wrap" justifyContent={{ xs: 'flex-start', sm: 'flex-end' }}>
              <Chip 
                icon={<AssessmentIcon />}
                label={`${filteredSignals.length} Signals`} 
                color="primary" 
                size={isMobile ? "medium" : "small"}
              />
              <IconButton
                onClick={fetchSignals}
                disabled={loading}
                size={isMobile ? "medium" : "small"}
                sx={{ 
                  bgcolor: 'background.paper',
                  '&:hover': { bgcolor: 'action.hover' }
                }}
              >
                <RefreshIcon />
              </IconButton>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Mobile-Optimized Filters */}
      <Paper sx={{ p: { xs: 2, sm: 3 }, mb: { xs: 2, sm: 3 } }}>
        <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
          🔍 Filter Opportunities
        </Typography>
        
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          {/* Search */}
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              size={isMobile ? "medium" : "small"}
              label="Search Symbol"
              value={filters.searchText}
              onChange={(e) => setFilters(prev => ({ ...prev, searchText: e.target.value }))}
              placeholder="e.g., BTC, ETH"
              sx={{
                '& .MuiInputBase-root': {
                  fontSize: { xs: '16px', sm: '14px' } // Prevents zoom on iOS
                }
              }}
            />
          </Grid>

          {/* Precision Score */}
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              size={isMobile ? "medium" : "small"}
              type="number"
              label="Min Precision Score"
              value={filters.minPrecisionScore}
              onChange={(e) => setFilters(prev => ({ ...prev, minPrecisionScore: Number(e.target.value) }))}
              inputProps={{ min: 0, max: 100, step: 5 }}
              sx={{
                '& .MuiInputBase-root': {
                  fontSize: { xs: '16px', sm: '14px' }
                }
              }}
            />
          </Grid>

          {/* Move Range */}
          <Grid item xs={12} sm={6} md={4}>
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Move Range: {filters.minMove}% - {filters.maxMove}%
              </Typography>
              <Stack direction="row" spacing={2} alignItems="center">
                <TextField
                  size="small"
                  type="number"
                  label="Min %"
                  value={filters.minMove}
                  onChange={(e) => setFilters(prev => ({ ...prev, minMove: Number(e.target.value) }))}
                  inputProps={{ min: 0, max: 20, step: 0.1 }}
                  sx={{ 
                    width: '80px',
                    '& .MuiInputBase-root': {
                      fontSize: { xs: '16px', sm: '14px' }
                    }
                  }}
                />
                <TextField
                  size="small"
                  type="number"
                  label="Max %"
                  value={filters.maxMove}
                  onChange={(e) => setFilters(prev => ({ ...prev, maxMove: Number(e.target.value) }))}
                  inputProps={{ min: 0, max: 20, step: 0.1 }}
                  sx={{ 
                    width: '80px',
                    '& .MuiInputBase-root': {
                      fontSize: { xs: '16px', sm: '14px' }
                    }
                  }}
                />
              </Stack>
            </Box>
          </Grid>

          {/* High Certainty Toggle */}
          <Grid item xs={12} sm={6} md={4}>
            <FormControl component="fieldset">
              <FormControlLabel
                control={
                  <Switch
                    checked={filters.showOnlyHighCertainty}
                    onChange={(e) => setFilters(prev => ({ ...prev, showOnlyHighCertainty: e.target.checked }))}
                    color="primary"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      High Certainty Only
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      GUARANTEED • VERY HIGH • HIGH
                    </Typography>
                  </Box>
                }
              />
            </FormControl>
          </Grid>

          {/* Quick Actions */}
          <Grid item xs={12} sm={6} md={4}>
            <Stack direction="row" spacing={1} flexWrap="wrap" gap={1}>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setFilters({
                  minPrecisionScore: 80,
                  maxMove: 3.5,
                  minMove: 2.5,
                  minConfidence: 0.7,
                  searchText: '',
                  showOnlyHighCertainty: true
                })}
                sx={{ 
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                  minHeight: { xs: '36px', sm: '32px' }
                }}
              >
                🎯 Perfect 3%
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setFilters({
                  minPrecisionScore: 0,
                  maxMove: 10.0,
                  minMove: 0.5,
                  minConfidence: 0.0,
                  searchText: '',
                  showOnlyHighCertainty: false
                })}
                sx={{ 
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                  minHeight: { xs: '36px', sm: '32px' }
                }}
              >
                🔄 Reset
              </Button>
            </Stack>
          </Grid>
        </Grid>
      </Paper>

      {/* Results */}
      {filteredSignals.length === 0 ? (
        <Paper sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No opportunities match your filters
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your filter criteria or check back later
          </Typography>
        </Paper>
      ) : (
        <Box>
          {/* Mobile: Card Layout, Desktop: Keep existing layout */}
          {isMobile ? (
            <Stack spacing={2}>
              {filteredSignals.map((signal, index) => (
                <SignalCard 
                  key={`${signal.symbol}-${index}`} 
                  signal={signal} 
                  onDetailsClick={handleDetailsClick}
                />
              ))}
            </Stack>
          ) : (
            <Grid container spacing={2}>
              {filteredSignals.map((signal, index) => (
                <Grid item xs={12} sm={6} lg={4} key={`${signal.symbol}-${index}`}>
                  <SignalCard 
                    signal={signal} 
                    onDetailsClick={handleDetailsClick}
                  />
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}

      {/* Mobile-Optimized Signal Details Dialog */}
      <Dialog
        open={detailsOpen}
        onClose={handleCloseDetails}
        maxWidth="md"
        fullWidth
        fullScreen={isMobile}
        sx={{
          '& .MuiDialog-paper': {
            margin: { xs: 0, sm: '32px' },
            maxHeight: { xs: '100%', sm: 'calc(100% - 64px)' },
            borderRadius: { xs: 0, sm: '12px' }
          }
        }}
      >
        <DialogTitle sx={{ 
          p: { xs: 2, sm: 3 },
          borderBottom: '1px solid',
          borderColor: 'divider'
        }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" fontWeight="bold">
              {selectedSignal?.symbol} Signal Details
            </Typography>
            <IconButton 
              onClick={handleCloseDetails}
              size={isMobile ? "medium" : "small"}
            >
              <InfoIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        
        <DialogContent sx={{ p: { xs: 2, sm: 3 } }}>
          {selectedSignal && (
            <Box>
              {/* Certainty Badge */}
              <Box mb={3} textAlign="center">
                <CertaintyBadge signal={selectedSignal} />
              </Box>

              {/* Key Metrics */}
              <Grid container spacing={2} mb={3}>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'background.default' }}>
                    <Typography variant="caption" color="text.secondary">Entry Price</Typography>
                    <Typography variant="h6" fontWeight="bold">
                      ${(selectedSignal.entry || selectedSignal.entry_price || 0).toFixed(6)}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'success.light' }}>
                    <Typography variant="caption" color="text.secondary">Take Profit</Typography>
                    <Typography variant="h6" fontWeight="bold" color="success.dark">
                      ${(selectedSignal.take_profit || selectedSignal.takeProfit || 0).toFixed(6)}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'error.light' }}>
                    <Typography variant="caption" color="text.secondary">Stop Loss</Typography>
                    <Typography variant="h6" fontWeight="bold" color="error.dark">
                      ${(selectedSignal.stop_loss || selectedSignal.stopLoss || 0).toFixed(6)}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'warning.light' }}>
                    <Typography variant="caption" color="text.secondary">Expected Move</Typography>
                    <Typography variant="h6" fontWeight="bold" color="warning.dark">
                      {(Math.abs(((selectedSignal.take_profit || selectedSignal.takeProfit || 0) - (selectedSignal.entry || selectedSignal.entry_price || 0)) / (selectedSignal.entry || selectedSignal.entry_price || 1)) * 100).toFixed(2)}%
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              {/* Profit Calculator */}
              <ProfitCalculator signal={selectedSignal} />

              {/* Precision Score */}
              <Box mt={3} textAlign="center">
                <PrecisionBadge signal={selectedSignal} />
              </Box>
            </Box>
          )}
        </DialogContent>
        
        <DialogActions sx={{ 
          p: { xs: 2, sm: 3 },
          borderTop: '1px solid',
          borderColor: 'divider',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: { xs: 1, sm: 0 }
        }}>
          <Button 
            onClick={handleCloseDetails}
            variant="outlined"
            fullWidth={isMobile}
          >
            Close
          </Button>
          <Button 
            variant="contained" 
            color="primary"
            fullWidth={isMobile}
            sx={{ ml: { xs: 0, sm: 1 } }}
          >
            Track Signal
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Opportunities; 