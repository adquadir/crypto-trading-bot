import React, { useState, useEffect, useCallback } from 'react';
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
  InputAdornment,
  Alert
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
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip as ChartTooltip,
  Legend
} from 'chart.js';
import config from '../config';
import { useWebSocket } from '../contexts/WebSocketContext';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  ChartTooltip,
  Legend
);

const getFreshnessColor = (age) => {
  if (age <= 5) return 'success';
  if (age <= 10) return 'warning';
  return 'error';
};

const formatAge = (age) => {
  if (age < 1) return `${(age * 1000).toFixed(0)}ms`;
  return `${age.toFixed(1)}s`;
};

const TimeframeComparison = ({ signal }) => {
  const chartData = {
    labels: ['1m', '5m', '15m'],
    datasets: [
      {
        label: 'Technical Alignment',
        data: signal.mtf_alignment?.details?.technical?.scores || [],
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1
      },
      {
        label: 'Volume Alignment',
        data: signal.mtf_alignment?.details?.volume?.scores || [],
        borderColor: 'rgb(255, 99, 132)',
        tension: 0.1
      },
      {
        label: 'Pattern Alignment',
        data: signal.mtf_alignment?.details?.patterns?.scores || [],
        borderColor: 'rgb(54, 162, 235)',
        tension: 0.1
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
        text: 'Timeframe Alignment Analysis'
      }
    },
    scales: {
      y: {
        min: -1,
        max: 1,
        title: {
          display: true,
          text: 'Alignment Score'
        }
      }
    }
  };

  return (
    <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
      <Line data={chartData} options={options} />
    </Box>
  );
};

const VolumeAnalysis = ({ signal }) => {
  const volumeData = {
    labels: ['1m', '5m', '15m'],
    datasets: [
      {
        label: 'Volume Profile',
        data: signal.mtf_alignment?.details?.volume?.analysis?.map(a => a.profile.score) || [],
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
        borderColor: 'rgb(75, 192, 192)',
        borderWidth: 1
      },
      {
        label: 'Volume Delta',
        data: signal.mtf_alignment?.details?.volume?.analysis?.map(a => a.delta.score) || [],
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
        borderColor: 'rgb(255, 99, 132)',
        borderWidth: 1
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
        text: 'Volume Analysis'
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Score'
        }
      }
    }
  };

  return (
    <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
      <Bar data={volumeData} options={options} />
    </Box>
  );
};

const PatternAnalysis = ({ signal }) => {
  const patterns = signal.mtf_alignment?.details?.patterns?.types || [];
  
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" color="textSecondary" gutterBottom>
        Detected Patterns
      </Typography>
      <Box display="flex" gap={1} flexWrap="wrap">
        {patterns.map((pattern, index) => (
          <Chip
            key={index}
            label={pattern.type}
            color={pattern.strength > 0.8 ? 'success' : pattern.strength > 0.6 ? 'warning' : 'default'}
            variant="outlined"
            sx={{ m: 0.5 }}
          />
        ))}
      </Box>
    </Box>
  );
};

const DataFreshnessPanel = ({ opportunity }) => {
  if (!opportunity.data_freshness) return null;

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" color="textSecondary" gutterBottom>
        Data Freshness
      </Typography>
      <Grid container spacing={1}>
        {Object.entries(opportunity.data_freshness).map(([type, age]) => (
          <Grid item xs={6} sm={4} key={type}>
            <Chip
              label={`${type}: ${formatAge(age)}`}
              color={getFreshnessColor(age)}
              size="small"
              sx={{ m: 0.5 }}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

const Opportunities = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [viewMode, setViewMode] = useState('table');
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
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let ws = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.WS_SIGNALS}`);
    
    const attachHandlers = (socket) => {
        socket.onopen = () => {
            console.log('WebSocket connected');
            setWsConnected(true);
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'opportunities') {
                setOpportunities(data.data);
            }
        };

        socket.onclose = () => {
            console.log('WebSocket disconnected');
            setWsConnected(false);
            
            // Attempt to reconnect after a delay
            setTimeout(() => {
                console.log('Attempting to reconnect WebSocket...');
                const newWs = new WebSocket(`${config.WS_BASE_URL}${config.ENDPOINTS.WS_SIGNALS}`);
                attachHandlers(newWs);  // Reattach handlers to new instance
                ws = newWs;  // Replace the old WebSocket instance
            }, 5000);
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            setError('WebSocket connection error');
        };
    };

    // Attach handlers to initial WebSocket
    attachHandlers(ws);

    return () => {
        ws.close();
    };
}, []);

  useEffect(() => {
    if (wsConnected) {
      console.log('WebSocket connected, ready to receive data');
    }
  }, [wsConnected]);

  const fetchOpportunities = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITIES}`);
      setOpportunities(response.data.data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch opportunities');
      console.error('Error fetching opportunities:', err);
    } finally {
      setLoading(false);
    }
  };

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

  const renderTimeframeDetails = (opp) => {
    if (!opp.mtf_alignment?.details) return null;

    return (
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" color="textSecondary" gutterBottom>
          Timeframe Analysis
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TimeframeComparison signal={opp} />
          </Grid>
          <Grid item xs={12}>
            <VolumeAnalysis signal={opp} />
          </Grid>
          <Grid item xs={12}>
            <PatternAnalysis signal={opp} />
          </Grid>
          <Grid item xs={12}>
            <Box display="flex" gap={1} flexWrap="wrap">
              {Object.entries(opp.mtf_alignment.details).map(([category, data]) => (
                <Chip
                  key={category}
                  label={`${category}: ${data.trend}`}
                  color={getTimeframeColor(data.score)}
                  size="small"
                  sx={{ m: 0.5 }}
                />
              ))}
            </Box>
          </Grid>
        </Grid>
      </Box>
    );
  };

  const renderCard = (opp) => (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">{opp.symbol}</Typography>
          <Box display="flex" gap={1}>
            <Chip
              icon={getDirectionIcon(opp.signal_type)}
              label={opp.signal_type}
              color={getDirectionColor(opp.signal_type)}
              size="small"
            />
            <Chip
              label={opp.regime}
              color={getRegimeColor(opp.regime)}
              size="small"
            />
          </Box>
        </Box>
        {renderChart(opp)}
        <Box mt={2}>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="body2" color="textSecondary">Entry</Typography>
              <Typography variant="body1">${opp.entry.toFixed(6)}</Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="body2" color="textSecondary">Confidence</Typography>
              <Typography variant="body1">{(opp.confidence_score * 100).toFixed(1)}%</Typography>
            </Grid>
            {renderTimeframeDetails(opp)}
          </Grid>
        </Box>
      </CardContent>
    </Card>
  );

  const renderTable = () => (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Signal Type</TableCell>
            <TableCell>Regime</TableCell>
            <TableCell>MTF Align</TableCell>
            <TableCell>Patterns</TableCell>
            <TableCell>Volume</TableCell>
            <TableCell>Entry</TableCell>
            <TableCell>SL</TableCell>
            <TableCell>TP</TableCell>
            <TableCell>Confidence</TableCell>
            <TableCell>RR</TableCell>
            <TableCell>Freshness</TableCell>
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
              <TableCell>
                <Chip
                  label={opp.regime}
                  color={getRegimeColor(opp.regime)}
                  size="small"
                />
              </TableCell>
              <TableCell>
                <Box display="flex" gap={0.5}>
                  {opp.mtf_alignment?.details && Object.entries(opp.mtf_alignment.details).map(([category, data]) => (
                    <Chip
                      key={category}
                      label={`${category[0]}:${data.score.toFixed(1)}`}
                      color={getTimeframeColor(data.score)}
                      size="small"
                    />
                  ))}
                </Box>
              </TableCell>
              <TableCell>
                <Box display="flex" gap={0.5}>
                  {opp.mtf_alignment?.details?.patterns?.types?.map((pattern, index) => (
                    <Chip
                      key={index}
                      label={pattern.type}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                </Box>
              </TableCell>
              <TableCell>
                <Box display="flex" gap={0.5}>
                  {opp.mtf_alignment?.details?.volume?.analysis?.map((analysis, index) => (
                    <Chip
                      key={index}
                      label={`${analysis.timeframe}:${analysis.trend.direction}`}
                      color={analysis.trend.direction === 'INCREASING' ? 'success' : 'error'}
                      size="small"
                    />
                  ))}
                </Box>
              </TableCell>
              <TableCell>${opp.entry.toFixed(6)}</TableCell>
              <TableCell>${opp.stop_loss.toFixed(6)}</TableCell>
              <TableCell>${opp.take_profit.toFixed(6)}</TableCell>
              <TableCell>{(opp.confidence_score * 100).toFixed(1)}%</TableCell>
              <TableCell>{opp.risk_reward.toFixed(2)}</TableCell>
              <TableCell>
                {opp.data_freshness && (
                  <Box display="flex" gap={0.5}>
                    {Object.entries(opp.data_freshness).map(([type, age]) => (
                      <Chip
                        key={type}
                        label={`${type[0]}:${age.toFixed(1)}s`}
                        color={getFreshnessColor(age)}
                        size="small"
                      />
                    ))}
                  </Box>
                )}
              </TableCell>
              <TableCell>
                <IconButton
                  size="small"
                  onClick={() => {
                    setSelectedOpportunity(opp);
                    setDetailsOpen(true);
                  }}
                >
                  <InfoIcon />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

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
        renderTable()
      ) : (
        <Grid container spacing={3}>
          {filteredAndSortedOpportunities.map((opp) => (
            <Grid item xs={12} md={6} key={opp.symbol}>
              {renderCard(opp)}
            </Grid>
          ))}
        </Grid>
      )}

      {/* Details Dialog */}
      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        {selectedOpportunity && (
          <DialogContent>
            <Box p={2}>
              <Typography variant="h6" gutterBottom>
                {selectedOpportunity.symbol} Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  {renderChart(selectedOpportunity)}
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Signal Type</Typography>
                  <Typography variant="body1">{selectedOpportunity.signal_type}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Market Regime</Typography>
                  <Typography variant="body1">{selectedOpportunity.regime}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Entry Price</Typography>
                  <Typography variant="body1">${selectedOpportunity.entry.toFixed(6)}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Stop Loss</Typography>
                  <Typography variant="body1">${selectedOpportunity.stop_loss.toFixed(6)}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Take Profit</Typography>
                  <Typography variant="body1">${selectedOpportunity.take_profit.toFixed(6)}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="textSecondary">Risk/Reward</Typography>
                  <Typography variant="body1">
                    {((selectedOpportunity.take_profit - selectedOpportunity.entry) / 
                      (selectedOpportunity.entry - selectedOpportunity.stop_loss)).toFixed(2)}
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="body2" color="textSecondary">Timeframe Alignment</Typography>
                  <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                    {selectedOpportunity.mtf_alignment?.details && 
                      Object.entries(selectedOpportunity.mtf_alignment.details).map(([tf, data]) => (
                        <Chip
                          key={tf}
                          label={`${tf}: ${data.direction} (${data.strength.toFixed(2)})`}
                          color={getTimeframeColor(data.strength)}
                          size="small"
                        />
                    ))}
                  </Box>
                </Grid>
                {selectedOpportunity.reasons && selectedOpportunity.reasons.length > 0 && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="textSecondary">Signal Reasons</Typography>
                    <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                      {selectedOpportunity.reasons.map((reason, index) => (
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
                <Grid item xs={12}>
                  <DataFreshnessPanel opportunity={selectedOpportunity} />
                </Grid>
              </Grid>
            </Box>
          </DialogContent>
        )}
      </Dialog>
    </Box>
  );
};

export default Opportunities; 