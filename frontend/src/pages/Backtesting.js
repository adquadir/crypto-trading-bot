import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
  const [runningTasks, setRunningTasks] = useState({});

  // Load available strategies and symbols
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [strategiesRes, symbolsRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/backtesting/strategies`),
          fetch(`${API_URL}/api/v1/backtesting/symbols`)
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
      const response = await fetch(`${API_URL}/api/v1/backtesting/run`, {
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
      const response = await fetch(`${API_URL}/api/v1/backtesting/compare`, {
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

  const getRatingColor = (rating) => {
    if (rating.includes('⭐⭐⭐⭐⭐')) return 'bg-green-500';
    if (rating.includes('⭐⭐⭐⭐')) return 'bg-blue-500';
    if (rating.includes('⭐⭐⭐')) return 'bg-yellow-500';
    if (rating.includes('⭐⭐')) return 'bg-orange-500';
    if (rating.includes('⭐')) return 'bg-red-500';
    return 'bg-gray-500';
  };

  const formatPercentage = (value) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatCurrency = (value) => {
    return `$${value.toFixed(2)}`;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Strategy Backtesting</h1>
        <Badge variant="outline" className="text-green-600">
          🎯 Production Ready
        </Badge>
      </div>

      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertDescription className="text-red-800">
            {error}
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="single" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="single">Single Strategy Test</TabsTrigger>
          <TabsTrigger value="compare">Strategy Comparison</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>🚀 Single Strategy Backtest</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Strategy</label>
                  <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select strategy" />
                    </SelectTrigger>
                    <SelectContent>
                      {strategies.map((strategy) => (
                        <SelectItem key={strategy.name} value={strategy.name}>
                          {strategy.name} - {strategy.risk_level}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Symbol</label>
                  <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select symbol" />
                    </SelectTrigger>
                    <SelectContent>
                      {symbols.map((symbol) => (
                        <SelectItem key={symbol.symbol} value={symbol.symbol}>
                          {symbol.symbol} - {symbol.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Days Back</label>
                  <Input
                    type="number"
                    value={daysBack}
                    onChange={(e) => setDaysBack(parseInt(e.target.value))}
                    min="1"
                    max="365"
                  />
                </div>
              </div>

              <Button 
                onClick={runSingleBacktest} 
                disabled={loading || !selectedStrategy || !selectedSymbol}
                className="w-full"
              >
                {loading ? 'Running Backtest...' : '🚀 Run Backtest'}
              </Button>

              {results && (
                <Card className="mt-6">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      📊 Backtest Results
                      <Badge className="ml-2">
                        {results.strategy} on {results.symbol}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">
                          {formatPercentage(results.performance.total_return)}
                        </div>
                        <div className="text-sm text-gray-600">Total Return</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">
                          {formatPercentage(results.performance.win_rate)}
                        </div>
                        <div className="text-sm text-gray-600">Win Rate</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">
                          {results.performance.total_trades}
                        </div>
                        <div className="text-sm text-gray-600">Total Trades</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-orange-600">
                          {results.performance.sharpe_ratio.toFixed(2)}
                        </div>
                        <div className="text-sm text-gray-600">Sharpe Ratio</div>
                      </div>
                    </div>

                    <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {formatPercentage(results.performance.max_drawdown)}
                        </div>
                        <div className="text-sm text-gray-600">Max Drawdown</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {results.performance.profit_factor.toFixed(2)}
                        </div>
                        <div className="text-sm text-gray-600">Profit Factor</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-semibold">
                          {formatCurrency(results.performance.best_trade)}
                        </div>
                        <div className="text-sm text-gray-600">Best Trade</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="compare" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>⚔️ Strategy Comparison</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Symbol</label>
                  <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select symbol" />
                    </SelectTrigger>
                    <SelectContent>
                      {symbols.map((symbol) => (
                        <SelectItem key={symbol.symbol} value={symbol.symbol}>
                          {symbol.symbol} - {symbol.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Days Back</label>
                  <Input
                    type="number"
                    value={daysBack}
                    onChange={(e) => setDaysBack(parseInt(e.target.value))}
                    min="1"
                    max="365"
                  />
                </div>
              </div>

              <Button 
                onClick={runStrategyComparison} 
                disabled={loading || !selectedSymbol}
                className="w-full"
              >
                {loading ? 'Comparing Strategies...' : '⚔️ Compare All Strategies'}
              </Button>

              {comparison && (
                <Card className="mt-6">
                  <CardHeader>
                    <CardTitle>📊 Strategy Comparison Results</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full table-auto">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left p-2">Strategy</th>
                            <th className="text-left p-2">Win Rate</th>
                            <th className="text-left p-2">Total Return</th>
                            <th className="text-left p-2">Sharpe Ratio</th>
                            <th className="text-left p-2">Max Drawdown</th>
                            <th className="text-left p-2">Total Trades</th>
                          </tr>
                        </thead>
                        <tbody>
                          {comparison.comparison.map((row, index) => (
                            <tr key={index} className="border-b hover:bg-gray-50">
                              <td className="p-2 font-medium">{row.Strategy}</td>
                              <td className="p-2">{row['Win Rate']}</td>
                              <td className="p-2">
                                <span className={row['Total Return'].startsWith('-') ? 'text-red-600' : 'text-green-600'}>
                                  {row['Total Return']}
                                </span>
                              </td>
                              <td className="p-2">{row['Sharpe Ratio']}</td>
                              <td className="p-2">{row['Max Drawdown']}</td>
                              <td className="p-2">{row['Total Trades']}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>📚 Available Strategies</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {strategies.map((strategy) => (
              <Card key={strategy.name} className="border-l-4 border-blue-500">
                <CardContent className="p-4">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-semibold">{strategy.name}</h3>
                    <Badge variant="outline">{strategy.risk_level}</Badge>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{strategy.description}</p>
                  <div className="text-xs text-gray-500">
                    <div>Win Rate: {strategy.typical_win_rate}</div>
                    <div>Best Markets: {strategy.best_market_conditions}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Backtesting; 