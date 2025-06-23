import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Chip,
  Alert,
  Tabs,
  Tab,
  Box,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress
} from '@mui/material';
import config from '../config';

const Backtesting = () => {
  const [strategies, setStrategies] = useState([]);
  const [symbols, setSymbols] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [daysBack, setDaysBack] = useState(30);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(0);

  // Load available strategies and symbols
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [strategiesRes, symbolsRes] = await Promise.all([
          fetch(`${config.API_BASE_URL}/api/v1/backtesting/strategies`),
          fetch(`${config.API_BASE_URL}/api/v1/backtesting/symbols`)
        ]);

        if (strategiesRes.ok) {
          const strategiesData = await strategiesRes.json();
          setStrategies(strategiesData.strategies || []);
        }

        if (symbolsRes.ok) {
          const symbolsData = await symbolsRes.json();
          setSymbols(symbolsData.symbols || []);
        }
      } catch (err) {
        setError('Failed to load backtesting options');
      }
    };

    loadOptions();
  }, []);

  const runSingleBacktest = async () => {
    if (!selectedStrategy || !selectedSymbol) {
      setError('Please select both strategy and symbol');
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v1/backtesting/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy: selectedStrategy,
          symbol: selectedSymbol,
          days_back: daysBack,
          initial_balance: 10000
        })
      });

      if (response.ok) {
        const data = await response.json();
        setResults(data);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Backtest failed');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const runStrategyComparison = async () => {
    if (!selectedSymbol) {
      setError('Please select a symbol');
      return;
    }

    setLoading(true);
    setError('');
    setComparison(null);

    try {
      const allStrategies = strategies.map(s => s.name);
      const response = await fetch(`${config.API_BASE_URL}/api/v1/backtesting/compare`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategies: allStrategies,
          symbol: selectedSymbol,
          days_back: daysBack
        })
      });

      if (response.ok) {
        const data = await response.json();
        setComparison(data);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Strategy comparison failed');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatPercentage = (value) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatCurrency = (value) => {
    return `$${value.toFixed(2)}`;
  };

  const SingleStrategyTab = () => (
    <Card>
      <CardHeader
        title={
          <Typography variant="h6" component="div">
            🚀 Single Strategy Backtest
          </Typography>
        }
      />
      <CardContent>
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Strategy</InputLabel>
              <Select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                label="Strategy"
              >
                {strategies.map((strategy) => (
                  <MenuItem key={strategy.name} value={strategy.name}>
                    {strategy.name} - {strategy.risk_level}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Symbol</InputLabel>
              <Select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                label="Symbol"
              >
                {symbols.map((symbol) => (
                  <MenuItem key={symbol.symbol} value={symbol.symbol}>
                    {symbol.symbol} - {symbol.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Days Back"
              type="number"
              value={daysBack}
              onChange={(e) => setDaysBack(parseInt(e.target.value))}
              inputProps={{ min: 1, max: 365 }}
            />
          </Grid>
        </Grid>

        <Button
          variant="contained"
          size="large"
          fullWidth
          onClick={runSingleBacktest}
          disabled={loading || !selectedStrategy || !selectedSymbol}
          sx={{ mb: 3 }}
        >
          {loading ? (
            <>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              Running Backtest...
            </>
          ) : (
            '🚀 Run Backtest'
          )}
        </Button>

        {results && (
          <Card sx={{ mt: 3, bgcolor: 'background.paper' }}>
            <CardHeader
              title={
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Typography variant="h6">📊 Backtest Results</Typography>
                  <Chip label={`${results.strategy} on ${results.symbol}`} />
                </Box>
              }
            />
            <CardContent>
              <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={6} md={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="success.main" fontWeight="bold">
                      {formatPercentage(results.performance.total_return)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Return
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary.main" fontWeight="bold">
                      {formatPercentage(results.performance.win_rate)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Win Rate
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="secondary.main" fontWeight="bold">
                      {results.performance.total_trades}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Trades
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="warning.main" fontWeight="bold">
                      {results.performance.sharpe_ratio.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Sharpe Ratio
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              <Grid container spacing={3}>
                <Grid item xs={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h6" fontWeight="bold">
                      {formatPercentage(results.performance.max_drawdown)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Max Drawdown
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h6" fontWeight="bold">
                      {results.performance.profit_factor.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Profit Factor
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h6" fontWeight="bold">
                      {formatCurrency(results.performance.best_trade)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Best Trade
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );

  const StrategyComparisonTab = () => (
    <Card>
      <CardHeader
        title={
          <Typography variant="h6" component="div">
            ⚔️ Strategy Comparison
          </Typography>
        }
      />
      <CardContent>
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Symbol</InputLabel>
              <Select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                label="Symbol"
              >
                {symbols.map((symbol) => (
                  <MenuItem key={symbol.symbol} value={symbol.symbol}>
                    {symbol.symbol} - {symbol.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Days Back"
              type="number"
              value={daysBack}
              onChange={(e) => setDaysBack(parseInt(e.target.value))}
              inputProps={{ min: 1, max: 365 }}
            />
          </Grid>
        </Grid>

        <Button
          variant="contained"
          size="large"
          fullWidth
          onClick={runStrategyComparison}
          disabled={loading || !selectedSymbol}
          sx={{ mb: 3 }}
        >
          {loading ? (
            <>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              Comparing Strategies...
            </>
          ) : (
            '⚔️ Compare All Strategies'
          )}
        </Button>

        {comparison && (
          <Card sx={{ mt: 3 }}>
            <CardHeader
              title={
                <Typography variant="h6">📊 Strategy Comparison Results</Typography>
              }
            />
            <CardContent>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Strategy</TableCell>
                      <TableCell>Win Rate</TableCell>
                      <TableCell>Total Return</TableCell>
                      <TableCell>Sharpe Ratio</TableCell>
                      <TableCell>Max Drawdown</TableCell>
                      <TableCell>Total Trades</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {comparison.comparison.map((row, index) => (
                      <TableRow key={index} hover>
                        <TableCell>
                          <Typography fontWeight="medium">{row.Strategy}</Typography>
                        </TableCell>
                        <TableCell>{row['Win Rate']}</TableCell>
                        <TableCell>
                          <Typography
                            color={row['Total Return'].startsWith('-') ? 'error' : 'success.main'}
                          >
                            {row['Total Return']}
                          </Typography>
                        </TableCell>
                        <TableCell>{row['Sharpe Ratio']}</TableCell>
                        <TableCell>{row['Max Drawdown']}</TableCell>
                        <TableCell>{row['Total Trades']}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1" fontWeight="bold">
          Strategy Backtesting
        </Typography>
        <Chip label="🎯 Production Ready" variant="outlined" color="success" />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ width: '100%', mb: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={(e, value) => setActiveTab(value)}>
            <Tab label="Single Strategy Test" />
            <Tab label="Strategy Comparison" />
          </Tabs>
        </Box>

        <Box sx={{ pt: 3 }}>
          {activeTab === 0 && <SingleStrategyTab />}
          {activeTab === 1 && <StrategyComparisonTab />}
        </Box>
      </Box>

      <Card>
        <CardHeader
          title={
            <Typography variant="h6" component="div">
              📚 Available Strategies
            </Typography>
          }
        />
        <CardContent>
          <Grid container spacing={2}>
            {strategies.map((strategy) => (
              <Grid item xs={12} md={6} key={strategy.name}>
                <Card variant="outlined" sx={{ borderLeft: 4, borderLeftColor: 'primary.main' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                      <Typography variant="h6" component="h3">
                        {strategy.name}
                      </Typography>
                      <Chip label={strategy.risk_level} variant="outlined" size="small" />
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {strategy.description}
                    </Typography>
                    <Box sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
                      <Typography variant="caption" display="block">
                        Win Rate: {strategy.typical_win_rate}
                      </Typography>
                      <Typography variant="caption" display="block">
                        Best Markets: {strategy.best_market_conditions}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Backtesting; 