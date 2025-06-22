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
  Stack
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
    return calculatePrecisionScore(b) - calculatePrecisionScore(a);
  });

  const handleDetailsClick = (signal) => {
    setSelectedSignal(signal);
    setDetailsOpen(true);
  };

  if (loading && signals.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: isMobile ? 1 : 2 }}>
      {/* Header - Mobile Optimized */}
      <Box mb={3}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box flex={1}>
            <Typography variant={isMobile ? "h6" : "h5"} gutterBottom fontWeight="bold">
              🎯 3% Precision Trading
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ display: isMobile ? 'none' : 'block' }}>
              "Give me just 3% of movement — with precision, volume, and high probability — and I'll scale that into serious profit."
            </Typography>
          </Box>
          <IconButton onClick={fetchSignals} disabled={loading} color="primary">
            <RefreshIcon />
          </IconButton>
        </Box>
        
        {/* Mobile Stats Row */}
        <Stack direction="row" spacing={1} justifyContent="space-between" flexWrap="wrap" gap={1}>
          <Chip 
            icon={<SpeedIcon />} 
            label={`${filteredSignals.length} Signals`} 
            color="primary" 
            size="small"
          />
          <Chip 
            icon={<span>🟢</span>} 
            label={`${filteredSignals.filter(s => ['GUARANTEED', 'VERY HIGH', 'HIGH'].includes(s.certainty_label)).length} High-Certainty`} 
            color="success" 
            variant="filled"
            size="small"
          />
          {isMobile && (
            <Chip 
              icon={<AssessmentIcon />} 
              label={isMobile ? "Cards" : "Card View"}
              color="info"
              size="small"
            />
          )}
        </Stack>
      </Box>

      {/* Strategy Stats Grid - Responsive */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: isMobile ? 1.5 : 2 }}>
              <PrecisionIcon color="primary" sx={{ fontSize: isMobile ? 30 : 40, mb: 1 }} />
              <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">Precision Focus</Typography>
              <Typography variant="caption" color="textSecondary">
                2-4% moves only
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: isMobile ? 1.5 : 2 }}>
              <LeverageIcon color="success" sx={{ fontSize: isMobile ? 30 : 40, mb: 1 }} />
              <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">Leverage Ready</Typography>
              <Typography variant="caption" color="textSecondary">
                5x-15x amplification
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: isMobile ? 1.5 : 2 }}>
              <SpeedIcon color="warning" sx={{ fontSize: isMobile ? 30 : 40, mb: 1 }} />
              <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">Fast Execution</Typography>
              <Typography variant="caption" color="textSecondary">
                In/out &lt; 2 hours
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center', p: isMobile ? 1.5 : 2 }}>
              <ProfitIcon color="error" sx={{ fontSize: isMobile ? 30 : 40, mb: 1 }} />
              <Typography variant={isMobile ? "body2" : "h6"} fontWeight="bold">Compound Ready</Typography>
              <Typography variant="caption" color="textSecondary">
                Repeatable profits
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters - Mobile Optimized */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: isMobile ? 1.5 : 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            🔍 Precision Filters
          </Typography>
          <Grid container spacing={isMobile ? 1 : 2} alignItems="center">
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                label="Search Symbol"
                value={filters.searchText}
                onChange={(e) => setFilters(prev => ({ ...prev, searchText: e.target.value }))}
                size="small"
              />
            </Grid>
            <Grid item xs={6} md={2}>
              <TextField
                fullWidth
                label="Min Move %"
                type="number"
                value={filters.minMove}
                onChange={(e) => setFilters(prev => ({ ...prev, minMove: Number(e.target.value) }))}
                size="small"
                inputProps={{ step: 0.1, min: 0.5, max: 10 }}
              />
            </Grid>
            <Grid item xs={6} md={2}>
              <TextField
                fullWidth
                label="Max Move %"
                type="number"
                value={filters.maxMove}
                onChange={(e) => setFilters(prev => ({ ...prev, maxMove: Number(e.target.value) }))}
                size="small"
                inputProps={{ step: 0.1, min: 1, max: 20 }}
              />
            </Grid>
            <Grid item xs={6} md={2}>
              <TextField
                fullWidth
                label="Min Precision"
                type="number"
                value={filters.minPrecisionScore}
                onChange={(e) => setFilters(prev => ({ ...prev, minPrecisionScore: Number(e.target.value) }))}
                size="small"
                inputProps={{ min: 0, max: 100 }}
              />
            </Grid>
            <Grid item xs={6} md={2}>
              <TextField
                fullWidth
                label="Min Confidence"
                type="number"
                value={filters.minConfidence}
                onChange={(e) => setFilters(prev => ({ ...prev, minConfidence: Number(e.target.value) }))}
                size="small"
                inputProps={{ step: 0.1, min: 0, max: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant={filters.showOnlyHighCertainty ? "contained" : "outlined"}
                color={filters.showOnlyHighCertainty ? "success" : "primary"}
                onClick={() => setFilters(prev => ({ ...prev, showOnlyHighCertainty: !prev.showOnlyHighCertainty }))}
                startIcon={filters.showOnlyHighCertainty ? <span>🟢</span> : <span>🎯</span>}
                size="small"
                sx={{ height: '40px' }}
              >
                {isMobile ? (filters.showOnlyHighCertainty ? 'High ✓' : 'High Filter') : (filters.showOnlyHighCertainty ? 'High Certainty ON' : 'Show High Certainty')}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Responsive Content: Cards on Mobile, Table on Desktop */}
      {isMobile ? (
        /* Mobile Card View */
        <Box>
          {filteredSignals.map((signal, index) => (
            <SignalCard 
              key={signal.signal_id || index} 
              signal={signal} 
              onDetailsClick={handleDetailsClick}
            />
          ))}
        </Box>
      ) : (
        /* Desktop Table View */
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Symbol</TableCell>
                <TableCell>Direction</TableCell>
                <TableCell>Take Profit Certainty</TableCell>
                <TableCell>Entry Price</TableCell>
                <TableCell>Take Profit</TableCell>
                <TableCell>Stop Loss</TableCell>
                <TableCell>Move %</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Precision Score</TableCell>
                <TableCell>Risk:Reward</TableCell>
                <TableCell>Profit @ 10x</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredSignals.map((signal, index) => {
                const entry = signal.entry || signal.entry_price || 0;
                const tp = signal.take_profit || signal.takeProfit || 0;
                const sl = signal.stop_loss || signal.stopLoss || entry * 0.98; // Default 2% SL
                const confidence = signal.confidence || signal.confidence_score || 0;
                const movePct = Math.abs((tp - entry) / entry) * 100;
                const riskReward = Math.abs(tp - entry) / Math.abs(entry - sl);
                const profitAt10x = 500 * (movePct / 100) * 10;
                
                return (
                  <TableRow key={signal.signal_id || index} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight="bold">
                        {signal.symbol}
                      </Typography>
                      {signal.timestamp && (
                        <Typography variant="caption" color="textSecondary">
                          {new Date(signal.timestamp).toLocaleTimeString()}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        icon={getDirectionIcon(signal.direction)}
                        label={signal.direction}
                        color={getDirectionColor(signal.direction)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <CertaintyBadge signal={signal} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        ${entry.toFixed(6)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="success.main">
                        ${tp.toFixed(6)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="error.main">
                        ${sl.toFixed(6)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={`${movePct.toFixed(2)}%`}
                        color={movePct >= 2.5 && movePct <= 3.5 ? 'success' : 'warning'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {(confidence * 100).toFixed(1)}%
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <PrecisionBadge signal={signal} />
                    </TableCell>
                    <TableCell>
                      <Typography 
                        variant="body2" 
                        color={riskReward >= 2 ? 'success.main' : 'text.primary'}
                      >
                        {riskReward.toFixed(2)}:1
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="success.main" fontWeight="bold">
                        ${profitAt10x.toFixed(0)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Tooltip title="View Details">
                        <IconButton 
                          size="small" 
                          onClick={() => handleDetailsClick(signal)}
                        >
                          <InfoIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {filteredSignals.length === 0 && !loading && (
        <Box textAlign="center" py={4}>
          <Typography variant="h6" color="textSecondary">
            No 3% precision signals found
          </Typography>
          <Typography variant="body2" color="textSecondary" mt={1}>
            Adjust your filters or wait for new high-precision opportunities
          </Typography>
        </Box>
      )}

      {/* Signal Details Dialog - Mobile Optimized */}
      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
        fullScreen={isMobile}
      >
        <DialogTitle>
          🎯 3% Precision Signal Details: {selectedSignal?.symbol}
        </DialogTitle>
        <DialogContent>
          {selectedSignal && (
            <Box>
              <Grid container spacing={2} mb={3}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Direction</Typography>
                  <Chip
                    icon={getDirectionIcon(selectedSignal.direction)}
                    label={selectedSignal.direction}
                    color={getDirectionColor(selectedSignal.direction)}
                  />
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Precision Score</Typography>
                  <PrecisionBadge signal={selectedSignal} />
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="body2" color="textSecondary">Entry Price</Typography>
                  <Typography variant="h6">${(selectedSignal.entry || selectedSignal.entry_price || 0).toFixed(6)}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="body2" color="textSecondary">Take Profit</Typography>
                  <Typography variant="h6" color="success.main">${(selectedSignal.take_profit || selectedSignal.takeProfit || 0).toFixed(6)}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="body2" color="textSecondary">Stop Loss</Typography>
                  <Typography variant="h6" color="error.main">${(selectedSignal.stop_loss || selectedSignal.stopLoss || 0).toFixed(6)}</Typography>
                </Grid>
              </Grid>
              
              <ProfitCalculator signal={selectedSignal} />
              
              {selectedSignal.strategy && (
                <Box mt={2}>
                  <Typography variant="body2" color="textSecondary">Strategy</Typography>
                  <Typography variant="body1">{selectedSignal.strategy}</Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsOpen(false)} fullWidth={isMobile}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default Opportunities; 