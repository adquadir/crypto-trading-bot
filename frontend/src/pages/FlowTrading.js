import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Tooltip,
  IconButton,
  Badge
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  GridOn,
  Speed,
  Stop,
  PlayArrow,
  Assessment,
  Timeline,
  Refresh,
  Error as Emergency,
  Add,
  SwapHoriz,
  Warning
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import config from '../config';

const FlowTrading = () => {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);
  const [flowStatus, setFlowStatus] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [grids, setGrids] = useState([]);
  const [riskMetrics, setRiskMetrics] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Dialog states
  const [addSymbolDialog, setAddSymbolDialog] = useState(false);
  const [gridConfigDialog, setGridConfigDialog] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  
  // Form states
  const [newSymbol, setNewSymbol] = useState('');
  const [gridConfig, setGridConfig] = useState({
    levels: 5,
    spacingMultiplier: 1.0,
    positionSizeUsd: 50
  });

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        fetchFlowStatus(),
        fetchStrategies(),
        fetchGrids(),
        fetchRiskMetrics(),
        fetchPerformance()
      ]);
      setError(null);
    } catch (err) {
      setError('Failed to fetch data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchFlowStatus = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/status`);
      const data = await response.json();
      setFlowStatus(data);
    } catch (err) {
      console.error('Failed to fetch flow status:', err);
    }
  };

  const fetchStrategies = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/strategies`);
      const data = await response.json();
      setStrategies(data);
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
    }
  };

  const fetchGrids = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/grids`);
      const data = await response.json();
      setGrids(data);
    } catch (err) {
      console.error('Failed to fetch grids:', err);
    }
  };

  const fetchRiskMetrics = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/risk`);
      const data = await response.json();
      setRiskMetrics(data);
    } catch (err) {
      console.error('Failed to fetch risk metrics:', err);
    }
  };

  const fetchPerformance = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/performance`);
      const data = await response.json();
      setPerformance(data);
    } catch (err) {
      console.log('Performance data not available (using basic mode)');
    }
  };

  // Advanced features integration
  const fetchAdvancedSignals = async (symbol) => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/advanced/signals/${symbol}`);
      const data = await response.json();
      return data;
    } catch (err) {
      console.log('Advanced signals not available');
      return null;
    }
  };

  const handleAddSymbol = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/strategies/${newSymbol}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        setAddSymbolDialog(false);
        setNewSymbol('');
        fetchAllData();
      } else {
        throw new Error('Failed to start flow trading');
      }
    } catch (err) {
      setError('Failed to add symbol: ' + err.message);
    }
  };

  const handleStopStrategy = async (symbol) => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/strategies/${symbol}/stop`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchAllData();
      } else {
        throw new Error('Failed to stop strategy');
      }
    } catch (err) {
      setError('Failed to stop strategy: ' + err.message);
    }
  };

  const handleStartGrid = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/grids/${selectedSymbol}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          levels: gridConfig.levels,
          spacing_multiplier: gridConfig.spacingMultiplier,
          position_size_usd: gridConfig.positionSizeUsd
        })
      });
      if (response.ok) {
        setGridConfigDialog(false);
        fetchAllData();
      } else {
        throw new Error('Failed to start grid');
      }
    } catch (err) {
      setError('Failed to start grid: ' + err.message);
    }
  };

  const handleStopGrid = async (symbol) => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/grids/${symbol}/stop`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchAllData();
      } else {
        throw new Error('Failed to stop grid');
      }
    } catch (err) {
      setError('Failed to stop grid: ' + err.message);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/flow-trading/emergency-stop`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchAllData();
      } else {
        throw new Error('Failed to execute emergency stop');
      }
    } catch (err) {
      setError('Emergency stop failed: ' + err.message);
    }
  };

  const getStrategyColor = (strategy) => {
    switch (strategy) {
      case 'scalping': return theme.palette.success.main;
      case 'grid_trading': return theme.palette.primary.main;
      case 'disabled': return theme.palette.grey[500];
      default: return theme.palette.grey[400];
    }
  };

  const getRegimeColor = (regime) => {
    switch (regime) {
      case 'trending_up': return theme.palette.success.main;
      case 'trending_down': return theme.palette.error.main;
      case 'ranging': return theme.palette.info.main;
      case 'high_volatility': return theme.palette.warning.main;
      default: return theme.palette.grey[400];
    }
  };

  const getStrategyIcon = (strategy) => {
    switch (strategy) {
      case 'scalping': return <Speed />;
      case 'grid_trading': return <GridOn />;
      default: return <Stop />;
    }
  };

  const StatusCards = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Active Strategies</Typography>
            <Typography variant="h3" color="primary">
              {flowStatus?.active_strategies || 0}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
              <Chip label="Scalping" size="small" sx={{ mr: 1 }} />
              <Typography variant="body2">{flowStatus?.active_scalping || 0}</Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Active Grids</Typography>
            <Typography variant="h3" color="info.main">
              {flowStatus?.active_grids || 0}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
              <GridOn sx={{ mr: 1, fontSize: '1rem' }} />
              <Typography variant="body2">Grid Trading</Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Total Exposure</Typography>
            <Typography variant="h3" color="warning.main">
              ${flowStatus?.total_exposure_usd?.toFixed(0) || '0'}
            </Typography>
            <LinearProgress 
              variant="determinate" 
              value={Math.min((flowStatus?.total_exposure_usd || 0) / 1000 * 100, 100)} 
              sx={{ mt: 1 }}
            />
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Daily P&L</Typography>
            <Typography 
              variant="h3" 
              color={flowStatus?.daily_pnl >= 0 ? 'success.main' : 'error.main'}
            >
              ${flowStatus?.daily_pnl?.toFixed(2) || '0.00'}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Today's performance
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const StrategiesTable = () => (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Strategy</TableCell>
            <TableCell>Market Regime</TableCell>
            <TableCell>Uptime</TableCell>
            <TableCell>Switch Count</TableCell>
            <TableCell>Performance</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {strategies.map((strategy) => (
            <TableRow key={strategy.symbol}>
              <TableCell>
                <Typography variant="body2" fontWeight="bold">
                  {strategy.symbol}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip
                  icon={getStrategyIcon(strategy.current_strategy)}
                  label={strategy.current_strategy?.replace('_', ' ').toUpperCase()}
                  size="small"
                  sx={{ 
                    bgcolor: getStrategyColor(strategy.current_strategy) + '20',
                    color: getStrategyColor(strategy.current_strategy)
                  }}
                />
              </TableCell>
              <TableCell>
                <Chip
                  label={strategy.market_regime?.replace('_', ' ').toUpperCase()}
                  size="small"
                  sx={{ 
                    bgcolor: getRegimeColor(strategy.market_regime) + '20',
                    color: getRegimeColor(strategy.market_regime)
                  }}
                />
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {strategy.uptime_minutes?.toFixed(1)}m
                </Typography>
              </TableCell>
              <TableCell>
                <Badge badgeContent={strategy.switch_count} color="primary">
                  <SwapHoriz />
                </Badge>
              </TableCell>
              <TableCell>
                <Typography 
                  variant="body2"
                  color={strategy.performance_score >= 0 ? 'success.main' : 'error.main'}
                >
                  {strategy.performance_score?.toFixed(2) || '0.00'}
                </Typography>
              </TableCell>
              <TableCell>
                <Tooltip title="Stop Strategy">
                  <IconButton 
                    size="small" 
                    color="error"
                    onClick={() => handleStopStrategy(strategy.symbol)}
                  >
                    <Stop />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const GridsTable = () => (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Center Price</TableCell>
            <TableCell>Grid Spacing</TableCell>
            <TableCell>Levels</TableCell>
            <TableCell>Active Orders</TableCell>
            <TableCell>Filled Orders</TableCell>
            <TableCell>Profit</TableCell>
            <TableCell>Uptime</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {grids.map((grid) => (
            <TableRow key={grid.symbol}>
              <TableCell>
                <Typography variant="body2" fontWeight="bold">
                  {grid.symbol}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  ${grid.center_price?.toFixed(4)}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  ${grid.grid_spacing?.toFixed(6)}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {grid.total_levels}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" color="primary">
                  {grid.active_orders}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" color="success.main">
                  {grid.filled_orders}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography 
                  variant="body2"
                  color={grid.total_profit >= 0 ? 'success.main' : 'error.main'}
                >
                  ${grid.total_profit?.toFixed(4) || '0.0000'}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {grid.uptime_minutes?.toFixed(1)}m
                </Typography>
              </TableCell>
              <TableCell>
                <Tooltip title="Stop Grid">
                  <IconButton 
                    size="small" 
                    color="error"
                    onClick={() => handleStopGrid(grid.symbol)}
                  >
                    <Stop />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const RiskMetrics = () => (
    <Grid container spacing={3}>
      {riskMetrics && !riskMetrics.error && (
        <>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Portfolio Exposure</Typography>
                <Typography variant="h4" color="primary">
                  {riskMetrics.total_exposure_pct?.toFixed(1) || '0.0'}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(riskMetrics.total_exposure_pct || 0, 100)} 
                  sx={{ mt: 1 }}
                />
                <Typography variant="caption" color="textSecondary">
                  ${riskMetrics.total_exposure_usd?.toFixed(2) || '0.00'} USD
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Max Drawdown</Typography>
                <Typography variant="h4" color="error.main">
                  {riskMetrics.max_drawdown_pct?.toFixed(1) || '0.0'}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(riskMetrics.max_drawdown_pct || 0, 100)} 
                  color="error"
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Active Strategies</Typography>
                <Typography variant="h4" color="success.main">
                  {riskMetrics.active_strategies || 0}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Correlation: {riskMetrics.correlation_concentration?.toFixed(2) || '0.00'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </>
      )}
      {riskMetrics && riskMetrics.error && (
        <Grid item xs={12}>
          <Alert severity="warning">
            Risk manager not available
          </Alert>
        </Grid>
      )}
    </Grid>
  );

  const PerformanceMetrics = () => (
    <Grid container spacing={3}>
      {performance ? (
        <>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Daily Performance (Last 30 Days)</Typography>
                {performance.daily_performance?.length > 0 ? (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Date</TableCell>
                        <TableCell>P&L</TableCell>
                        <TableCell>Trades</TableCell>
                        <TableCell>Win Rate</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {performance.daily_performance.slice(0, 10).map((day, index) => (
                        <TableRow key={index}>
                          <TableCell>{day.date}</TableCell>
                          <TableCell 
                            sx={{ color: day.daily_pnl >= 0 ? 'success.main' : 'error.main' }}
                          >
                            ${day.daily_pnl?.toFixed(2)}
                          </TableCell>
                          <TableCell>{day.daily_trades}</TableCell>
                          <TableCell>{(day.avg_win_rate * 100)?.toFixed(1)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Typography variant="body2" color="textSecondary">
                    No performance data available
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Strategy Breakdown (Last 7 Days)</Typography>
                {performance.strategy_breakdown?.length > 0 ? (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Strategy</TableCell>
                        <TableCell>P&L</TableCell>
                        <TableCell>Trades</TableCell>
                        <TableCell>Win Rate</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {performance.strategy_breakdown.map((strategy, index) => (
                        <TableRow key={index}>
                          <TableCell>{strategy.strategy_type}</TableCell>
                          <TableCell 
                            sx={{ color: strategy.total_pnl >= 0 ? 'success.main' : 'error.main' }}
                          >
                            ${strategy.total_pnl?.toFixed(2)}
                          </TableCell>
                          <TableCell>{strategy.total_trades}</TableCell>
                          <TableCell>{(strategy.avg_win_rate * 100)?.toFixed(1)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Typography variant="body2" color="textSecondary">
                    No strategy data available
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </>
      ) : (
        <Grid item xs={12}>
          <Alert severity="info">
            Loading performance data...
          </Alert>
        </Grid>
      )}
    </Grid>
  );

  if (loading && !flowStatus) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Flow Trading Dashboard
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<Add />}
            onClick={() => setAddSymbolDialog(true)}
            sx={{ mr: 1 }}
          >
            Add Symbol
          </Button>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={fetchAllData}
            sx={{ mr: 1 }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<Emergency />}
            onClick={handleEmergencyStop}
          >
            Emergency Stop
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <StatusCards />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Active Strategies" />
          <Tab label="Grid Trading" />
          <Tab label="Risk Metrics" />
          <Tab label="Performance" />
        </Tabs>
      </Box>

      <Box sx={{ mt: 2 }}>
        {activeTab === 0 && <StrategiesTable />}
        {activeTab === 1 && <GridsTable />}
        {activeTab === 2 && <RiskMetrics />}
        {activeTab === 3 && <PerformanceMetrics />}
      </Box>

      <Dialog open={addSymbolDialog} onClose={() => setAddSymbolDialog(false)}>
        <DialogTitle>Add New Symbol to Flow Trading</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Symbol (e.g., BTCUSDT)"
            type="text"
            fullWidth
            variant="outlined"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddSymbolDialog(false)}>Cancel</Button>
          <Button onClick={handleAddSymbol} variant="contained">Add Symbol</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={gridConfigDialog} onClose={() => setGridConfigDialog(false)}>
        <DialogTitle>Configure Grid Trading</DialogTitle>
        <DialogContent>
          <TextField
            margin="dense"
            label="Number of Levels"
            type="number"
            fullWidth
            variant="outlined"
            value={gridConfig.levels}
            onChange={(e) => setGridConfig({...gridConfig, levels: parseInt(e.target.value)})}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Spacing Multiplier"
            type="number"
            step="0.1"
            fullWidth
            variant="outlined"
            value={gridConfig.spacingMultiplier}
            onChange={(e) => setGridConfig({...gridConfig, spacingMultiplier: parseFloat(e.target.value)})}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Position Size (USD)"
            type="number"
            fullWidth
            variant="outlined"
            value={gridConfig.positionSizeUsd}
            onChange={(e) => setGridConfig({...gridConfig, positionSizeUsd: parseFloat(e.target.value)})}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGridConfigDialog(false)}>Cancel</Button>
          <Button onClick={handleStartGrid} variant="contained">Start Grid</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default FlowTrading;
