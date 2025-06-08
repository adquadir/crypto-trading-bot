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
  Divider,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  ToggleButton,
  ToggleButtonGroup,
  Slider,
  InputAdornment
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  ShowChart as ChartIcon,
  FilterList as FilterIcon,
  Sort as SortIcon
} from '@mui/icons-material';
import axios from 'axios';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip as ChartTooltip,
  Legend
} from 'chart.js';
import config from '../config';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  ChartTooltip,
  Legend
);

const Opportunities = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [viewMode, setViewMode] = useState('table'); // 'table' or 'chart'
  const [filters, setFilters] = useState({
    signalType: 'all',
    minConfidence: 0,
    minRiskReward: 0,
    searchText: ''
  });
  const [sortConfig, setSortConfig] = useState({
    field: 'confidence_score',
    direction: 'desc'
  });

  const fetchOpportunities = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITIES}`);
      setOpportunities(response.data.opportunities);
      setError(null);
    } catch (err) {
      setError('Failed to fetch opportunities');
      console.error('Error fetching opportunities:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOpportunities();
    // Set up polling every 30 seconds
    const interval = setInterval(fetchOpportunities, 30000);
    return () => clearInterval(interval);
  }, []);

  const getDirectionColor = (direction) => {
    switch(direction) {
      case 'LONG':
      case 'SAFE_BUY':
        return 'success';
      case 'SHORT':
      case 'SAFE_SELL':
        return 'error';
      default:
        return 'default';
    }
  };

  const getDirectionIcon = (direction) => {
    switch(direction) {
      case 'LONG':
      case 'SAFE_BUY':
        return <TrendingUpIcon />;
      case 'SHORT':
      case 'SAFE_SELL':
        return <TrendingDownIcon />;
      default:
        return null;
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({ ...prev, [field]: value }));
  };

  const handleSort = (field) => {
    setSortConfig(prev => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleViewModeChange = (event, newMode) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  const filteredAndSortedOpportunities = opportunities
    .filter(opp => {
      const matchesSignalType = filters.signalType === 'all' || opp.signal_type === filters.signalType;
      const matchesConfidence = opp.confidence_score >= filters.minConfidence;
      const matchesRiskReward = ((opp.take_profit - opp.entry) / (opp.entry - opp.stop_loss)) >= filters.minRiskReward;
      const matchesSearch = opp.symbol.toLowerCase().includes(filters.searchText.toLowerCase());
      return matchesSignalType && matchesConfidence && matchesRiskReward && matchesSearch;
    })
    .sort((a, b) => {
      const multiplier = sortConfig.direction === 'asc' ? 1 : -1;
      switch (sortConfig.field) {
        case 'confidence_score':
          return (a.confidence_score - b.confidence_score) * multiplier;
        case 'risk_reward':
          return (((a.take_profit - a.entry) / (a.entry - a.stop_loss)) -
                 ((b.take_profit - b.entry) / (b.entry - b.stop_loss))) * multiplier;
        case 'potential_profit':
          return ((a.take_profit - a.entry) - (b.take_profit - b.entry)) * multiplier;
        default:
          return 0;
      }
    });

  const renderChart = (opportunity) => {
    if (!opportunity.price_history) return null;

    const data = {
      labels: opportunity.price_history.map((_, i) => i),
      datasets: [
        {
          label: 'Price',
          data: opportunity.price_history,
          borderColor: 'rgb(75, 192, 192)',
          tension: 0.1
        },
        {
          label: 'Entry',
          data: Array(opportunity.price_history.length).fill(opportunity.entry),
          borderColor: 'rgb(255, 99, 132)',
          borderDash: [5, 5],
          fill: false
        },
        {
          label: 'Take Profit',
          data: Array(opportunity.price_history.length).fill(opportunity.take_profit),
          borderColor: 'rgb(54, 162, 235)',
          borderDash: [5, 5],
          fill: false
        },
        {
          label: 'Stop Loss',
          data: Array(opportunity.price_history.length).fill(opportunity.stop_loss),
          borderColor: 'rgb(255, 159, 64)',
          borderDash: [5, 5],
          fill: false
        }
      ]
    };

    const options = {
      responsive: true,
      plugins: {
        legend: {
          position: 'top',
        },
        title: {
          display: true,
          text: `${opportunity.symbol} Price Action`
        }
      },
      scales: {
        y: {
          beginAtZero: false
        }
      }
    };

    return <Line data={data} options={options} />;
  };

  if (loading && opportunities.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          Trading Opportunities
        </Typography>
        <Box display="flex" gap={2}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            size="small"
          >
            <ToggleButton value="table">
              <FilterIcon />
            </ToggleButton>
            <ToggleButton value="chart">
              <ChartIcon />
            </ToggleButton>
          </ToggleButtonGroup>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchOpportunities} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Box mb={3}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Search Symbol"
              value={filters.searchText}
              onChange={(e) => handleFilterChange('searchText', e.target.value)}
              size="small"
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Signal Type</InputLabel>
              <Select
                value={filters.signalType}
                label="Signal Type"
                onChange={(e) => handleFilterChange('signalType', e.target.value)}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="SAFE_BUY">Safe Buy</MenuItem>
                <MenuItem value="SAFE_SELL">Safe Sell</MenuItem>
                <MenuItem value="LONG">Long</MenuItem>
                <MenuItem value="SHORT">Short</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <Typography gutterBottom>Min Confidence</Typography>
            <Slider
              value={filters.minConfidence}
              onChange={(_, value) => handleFilterChange('minConfidence', value)}
              min={0}
              max={1}
              step={0.1}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <Typography gutterBottom>Min Risk/Reward</Typography>
            <Slider
              value={filters.minRiskReward}
              onChange={(_, value) => handleFilterChange('minRiskReward', value)}
              min={0}
              max={5}
              step={0.1}
              valueLabelDisplay="auto"
            />
          </Grid>
        </Grid>
      </Box>

      {viewMode === 'table' ? (
        <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Symbol</TableCell>
                <TableCell>
                  Signal Type
                  <IconButton size="small" onClick={() => handleSort('signal_type')}>
                    <SortIcon fontSize="small" />
                  </IconButton>
                </TableCell>
                <TableCell>Entry Price</TableCell>
                <TableCell>Stop Loss</TableCell>
                <TableCell>Take Profit</TableCell>
                <TableCell>
                  Confidence
                  <IconButton size="small" onClick={() => handleSort('confidence_score')}>
                    <SortIcon fontSize="small" />
                  </IconButton>
                </TableCell>
                <TableCell>
                  Risk/Reward
                  <IconButton size="small" onClick={() => handleSort('risk_reward')}>
                    <SortIcon fontSize="small" />
                  </IconButton>
                </TableCell>
                <TableCell>Details</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredAndSortedOpportunities.map((opp) => (
                <TableRow key={opp.symbol}>
                  <TableCell>{opp.symbol}</TableCell>
                  <TableCell>
                    <Chip
                      icon={getDirectionIcon(opp.signal_type)}
                      label={opp.signal_type}
                      color={getDirectionColor(opp.signal_type)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>${opp.entry.toFixed(2)}</TableCell>
                  <TableCell>${opp.stop_loss.toFixed(2)}</TableCell>
                  <TableCell>${opp.take_profit.toFixed(2)}</TableCell>
                  <TableCell>
                    <Chip
                      label={`${(opp.confidence_score * 100).toFixed(1)}%`}
                      color={opp.confidence_score > 0.7 ? 'success' : opp.confidence_score > 0.4 ? 'warning' : 'error'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {((opp.take_profit - opp.entry) / (opp.entry - opp.stop_loss)).toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Tooltip title="View Details">
                      <IconButton size="small">
                        <InfoIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Grid container spacing={3}>
          {filteredAndSortedOpportunities.map((opp) => (
            <Grid item xs={12} md={6} key={opp.symbol}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6">{opp.symbol}</Typography>
                    <Chip
                      icon={getDirectionIcon(opp.signal_type)}
                      label={opp.signal_type}
                      color={getDirectionColor(opp.signal_type)}
                      size="small"
                    />
                  </Box>
                  {renderChart(opp)}
                  <Box mt={2}>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">Entry</Typography>
                        <Typography variant="body1">${opp.entry.toFixed(2)}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="textSecondary">Confidence</Typography>
                        <Typography variant="body1">{(opp.confidence_score * 100).toFixed(1)}%</Typography>
                      </Grid>
                    </Grid>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* ... existing details dialog ... */}
    </Box>
  );
};

export default Opportunities; 