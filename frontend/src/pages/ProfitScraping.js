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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Psychology,
  Timeline,
  TrendingUp,
  TrendingDown,
  GridOn,
  Assessment,
  Refresh,
  Settings,
  MonetizationOn,
  Speed,
  AutoFixHigh,
  SmartToy,
  AnalyticsOutlined
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import config from '../config';

const ProfitScraping = () => {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);
  const [scrapingStatus, setScrapingStatus] = useState(null);
  const [recentTrades, setRecentTrades] = useState([]);
  const [advancedSignals, setAdvancedSignals] = useState({});
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [performanceAnalytics, setPerformanceAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Dialog states
  const [settingsDialog, setSettingsDialog] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  
  // Settings
  const [settings, setSettings] = useState({
    autoOptimize: true,
    mlEnhanced: true,
    riskAdjusted: true,
    symbols: ['BTCUSDT', 'ETHUSDT']
  });

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 3000); // More frequent updates
    return () => clearInterval(interval);
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        fetchScrapingStatus(),
        fetchRecentTrades(),
        fetchAdvancedSignals(),
        fetchRiskAnalysis(),
        fetchPerformanceAnalytics()
      ]);
      setError(null);
    } catch (err) {
      setError('Failed to fetch data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchScrapingStatus = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.PROFIT_SCRAPING.STATUS}`);
      const data = await response.json();
      setScrapingStatus(data.status === 'success' ? data.data : data);
    } catch (err) {
      console.error('Failed to fetch scraping status:', err);
    }
  };

  const fetchRecentTrades = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.PROFIT_SCRAPING.RECENT_TRADES}`);
      const data = await response.json();
      setRecentTrades(data.trades || []);
    } catch (err) {
      console.error('Failed to fetch recent trades:', err);
    }
  };

  const fetchAdvancedSignals = async () => {
    try {
      const symbols = settings.symbols;
      const signalPromises = symbols.map(async (symbol) => {
        const response = await fetch(`${config.API_BASE_URL}/api/v1/profit-scraping/api/v1/advanced/signals/${symbol}`);
        const data = await response.json();
        return { symbol, data: data.data };
      });
      
      const results = await Promise.all(signalPromises);
      const signalsMap = {};
      results.forEach(({ symbol, data }) => {
        signalsMap[symbol] = data;
      });
      setAdvancedSignals(signalsMap);
    } catch (err) {
      console.error('Failed to fetch advanced signals:', err);
    }
  };

  const fetchRiskAnalysis = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/profit-scraping/api/v1/advanced/risk-analysis`);
      const data = await response.json();
      setRiskAnalysis(data.data);
    } catch (err) {
      console.error('Failed to fetch risk analysis:', err);
    }
  };

  const fetchPerformanceAnalytics = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/profit-scraping/api/v1/advanced/performance-analytics`);
      const data = await response.json();
      setPerformanceAnalytics(data.data);
    } catch (err) {
      console.error('Failed to fetch performance analytics:', err);
    }
  };

  const handleStartScraping = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.PROFIT_SCRAPING.START}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: settings.symbols,
          ml_enhanced: settings.mlEnhanced,
          risk_adjusted: settings.riskAdjusted,
          auto_optimize: settings.autoOptimize
        })
      });
      
      if (response.ok) {
        await fetchAllData();
      } else {
        throw new Error('Failed to start profit scraping');
      }
    } catch (err) {
      setError('Failed to start scraping: ' + err.message);
    }
  };

  const handleStopScraping = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.PROFIT_SCRAPING.STOP}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        await fetchAllData();
      } else {
        throw new Error('Failed to stop profit scraping');
      }
    } catch (err) {
      setError('Failed to stop scraping: ' + err.message);
    }
  };

  const handleOptimizePortfolio = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/profit-scraping/api/v1/advanced/optimize-portfolio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: settings.symbols,
          optimization_target: 'risk_adjusted_return'
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Show optimization results
        console.log('Portfolio optimization results:', data);
        await fetchAllData();
      }
    } catch (err) {
      setError('Portfolio optimization failed: ' + err.message);
    }
  };

  const StatusOverview = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <MonetizationOn sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6">Profit Scraping</Typography>
            </Box>
            <Typography variant="h3" color={scrapingStatus?.active ? 'success.main' : 'grey.500'}>
              {scrapingStatus?.active ? 'ACTIVE' : 'STOPPED'}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {scrapingStatus?.active_symbols || 0} symbols active
            </Typography>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Assessment sx={{ mr: 1, color: 'info.main' }} />
              <Typography variant="h6">Total Profit</Typography>
            </Box>
            <Typography variant="h3" color={scrapingStatus?.total_profit >= 0 ? 'success.main' : 'error.main'}>
              ${scrapingStatus?.total_profit?.toFixed(2) || '0.00'}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {scrapingStatus?.total_trades || 0} trades executed
            </Typography>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <SmartToy sx={{ mr: 1, color: 'secondary.main' }} />
              <Typography variant="h6">ML Enhancement</Typography>
            </Box>
            <Typography variant="h3" color={settings.mlEnhanced ? 'success.main' : 'grey.500'}>
              {settings.mlEnhanced ? 'ON' : 'OFF'}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {performanceAnalytics?.ml_accuracy ? `${(performanceAnalytics.ml_accuracy * 100).toFixed(1)}% accuracy` : 'No data'}
            </Typography>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Timeline sx={{ mr: 1, color: 'warning.main' }} />
              <Typography variant="h6">Win Rate</Typography>
            </Box>
            <Typography variant="h3" color="primary.main">
              {scrapingStatus?.win_rate ? `${(scrapingStatus.win_rate * 100).toFixed(1)}%` : '0.0%'}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Last 24 hours
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const MLSignalsPanel = () => (
    <Grid container spacing={3}>
      {Object.entries(advancedSignals).map(([symbol, signal]) => (
        <Grid item xs={12} md={6} key={symbol}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">{symbol}</Typography>
                <Chip 
                  label={signal?.signal || 'HOLD'}
                  color={signal?.signal === 'LONG' ? 'success' : signal?.signal === 'SHORT' ? 'error' : 'default'}
                  icon={signal?.signal === 'LONG' ? <TrendingUp /> : signal?.signal === 'SHORT' ? <TrendingDown /> : <GridOn />}
                />
              </Box>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Confidence Score
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={(signal?.confidence || 0) * 100} 
                  sx={{ height: 8, borderRadius: 4 }}
                />
                <Typography variant="caption" color="textSecondary">
                  {((signal?.confidence || 0) * 100).toFixed(1)}%
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Market Regime
                </Typography>
                <Chip 
                  label={signal?.market_regime || 'Unknown'}
                  size="small"
                  color={signal?.market_regime === 'trending_up' ? 'success' : 
                         signal?.market_regime === 'trending_down' ? 'error' : 'info'}
                />
              </Box>

              {signal?.reasoning && (
                <Box>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    AI Reasoning
                  </Typography>
                  <Typography variant="body2" sx={{ 
                    p: 1, 
                    bgcolor: 'grey.50', 
                    borderRadius: 1,
                    fontSize: '0.8rem',
                    maxHeight: '100px',
                    overflow: 'auto'
                  }}>
                    {signal.reasoning}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  const RiskAnalysisPanel = () => (
    <Grid container spacing={3}>
      {riskAnalysis && (
        <>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Portfolio VaR</Typography>
                <Typography variant="h4" color="error.main">
                  ${riskAnalysis.portfolio_var_1d?.toFixed(2) || '0.00'}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  1-day Value at Risk (95% confidence)
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" color="textSecondary">
                    5-day VaR: ${riskAnalysis.portfolio_var_5d?.toFixed(2) || '0.00'}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Sharpe Ratio</Typography>
                <Typography variant="h4" color="primary.main">
                  {riskAnalysis.sharpe_ratio?.toFixed(2) || '0.00'}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Risk-adjusted return
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" color="textSecondary">
                    Sortino: {riskAnalysis.sortino_ratio?.toFixed(2) || '0.00'}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Max Drawdown</Typography>
                <Typography variant="h4" color="warning.main">
                  {riskAnalysis.max_drawdown ? `${(riskAnalysis.max_drawdown * 100).toFixed(1)}%` : '0.0%'}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Historical maximum loss
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Stress Test Results</Typography>
                {riskAnalysis.stress_test_results && (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Scenario</TableCell>
                        <TableCell>Estimated Loss</TableCell>
                        <TableCell>Portfolio Impact</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(riskAnalysis.stress_test_results).map(([scenario, result]) => (
                        <TableRow key={scenario}>
                          <TableCell>{scenario.replace('_', ' ').toUpperCase()}</TableCell>
                          <TableCell sx={{ color: 'error.main' }}>
                            ${result.estimated_loss?.toFixed(2) || '0.00'}
                          </TableCell>
                          <TableCell>
                            {result.portfolio_impact ? `${(result.portfolio_impact * 100).toFixed(1)}%` : '0.0%'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </Grid>
        </>
      )}
    </Grid>
  );

  const RecentTradesPanel = () => (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Time</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Strategy</TableCell>
            <TableCell>Entry Price</TableCell>
            <TableCell>Exit Price</TableCell>
            <TableCell>Profit</TableCell>
            <TableCell>Confidence</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {recentTrades.slice(0, 10).map((trade, index) => (
            <TableRow key={index}>
              <TableCell>
                <Typography variant="body2">
                  {new Date(trade.timestamp).toLocaleTimeString()}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontWeight="bold">
                  {trade.symbol}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip 
                  label={trade.side}
                  size="small"
                  color={trade.side === 'LONG' ? 'success' : 'error'}
                />
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {trade.strategy?.replace('_', ' ').toUpperCase()}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  ${trade.entry_price?.toFixed(4)}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  ${trade.exit_price?.toFixed(4)}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography 
                  variant="body2"
                  color={trade.profit >= 0 ? 'success.main' : 'error.main'}
                  fontWeight="bold"
                >
                  ${trade.profit?.toFixed(4)}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {trade.confidence ? `${(trade.confidence * 100).toFixed(0)}%` : 'N/A'}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const ControlPanel = () => (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Profit Scraping Control</Typography>
          <Box>
            <Button
              variant="outlined"
              startIcon={<Settings />}
              onClick={() => setSettingsDialog(true)}
              sx={{ mr: 1 }}
            >
              Settings
            </Button>
            <Button
              variant="outlined"
              startIcon={<AutoFixHigh />}
              onClick={handleOptimizePortfolio}
              sx={{ mr: 1 }}
            >
              Optimize
            </Button>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={fetchAllData}
              sx={{ mr: 2 }}
            >
              Refresh
            </Button>
            {scrapingStatus?.active ? (
              <Button
                variant="contained"
                color="error"
                startIcon={<Stop />}
                onClick={handleStopScraping}
              >
                Stop Scraping
              </Button>
            ) : (
              <Button
                variant="contained"
                color="success"
                startIcon={<PlayArrow />}
                onClick={handleStartScraping}
              >
                Start Scraping
              </Button>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  if (loading && !scrapingStatus) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        <SmartToy sx={{ mr: 1, verticalAlign: 'middle' }} />
        Profit Scraping - REAL MONEY TRADING
      </Typography>

      {/* Real Money Warning */}
      <Alert severity="warning" sx={{ mb: 3 }}>
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          ⚠️ REAL MONEY TRADING WARNING
        </Typography>
        <Typography variant="body2">
          <strong>This page executes REAL trades with REAL money.</strong> Only use this after:
          <br />• Testing extensively with Paper Trading first
          <br />• Proving profitability in virtual environment
          <br />• Setting up proper API keys and funding
          <br />• Understanding all risks involved
        </Typography>
      </Alert>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <ControlPanel />
      <StatusOverview />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="ML Signals" icon={<Psychology />} />
          <Tab label="Risk Analysis" icon={<Assessment />} />
          <Tab label="Recent Trades" icon={<Timeline />} />
          <Tab label="Performance" icon={<AnalyticsOutlined />} />
        </Tabs>
      </Box>

      <Box sx={{ mt: 2 }}>
        {activeTab === 0 && <MLSignalsPanel />}
        {activeTab === 1 && <RiskAnalysisPanel />}
        {activeTab === 2 && <RecentTradesPanel />}
        {activeTab === 3 && performanceAnalytics && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>ML Performance Analytics</Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2">Strategy Rankings:</Typography>
                  <List dense>
                    {performanceAnalytics.strategy_rankings?.map((strategy, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <span style={{ fontWeight: 'bold' }}>#{index + 1}</span>
                        </ListItemIcon>
                        <ListItemText 
                          primary={strategy.name}
                          secondary={`Score: ${strategy.score?.toFixed(3)}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2">ML Model Performance:</Typography>
                  <Typography variant="body1">
                    Accuracy: {performanceAnalytics.ml_accuracy ? `${(performanceAnalytics.ml_accuracy * 100).toFixed(1)}%` : 'N/A'}
                  </Typography>
                  <Typography variant="body1">
                    Precision: {performanceAnalytics.ml_precision ? `${(performanceAnalytics.ml_precision * 100).toFixed(1)}%` : 'N/A'}
                  </Typography>
                  <Typography variant="body1">
                    Recall: {performanceAnalytics.ml_recall ? `${(performanceAnalytics.ml_recall * 100).toFixed(1)}%` : 'N/A'}
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        )}
      </Box>

      <Dialog open={settingsDialog} onClose={() => setSettingsDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Advanced Settings</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.mlEnhanced}
                  onChange={(e) => setSettings({...settings, mlEnhanced: e.target.checked})}
                />
              }
              label="ML Enhanced Signals"
            />
          </Box>
          <Box sx={{ mt: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.riskAdjusted}
                  onChange={(e) => setSettings({...settings, riskAdjusted: e.target.checked})}
                />
              }
              label="Risk Adjusted Position Sizing"
            />
          </Box>
          <Box sx={{ mt: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.autoOptimize}
                  onChange={(e) => setSettings({...settings, autoOptimize: e.target.checked})}
                />
              }
              label="Auto Portfolio Optimization"
            />
          </Box>
          <Box sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="Active Symbols (comma separated)"
              value={settings.symbols.join(', ')}
              onChange={(e) => setSettings({
                ...settings, 
                symbols: e.target.value.split(',').map(s => s.trim().toUpperCase())
              })}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsDialog(false)}>Cancel</Button>
          <Button onClick={() => setSettingsDialog(false)} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ProfitScraping;
