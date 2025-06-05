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
  CircularProgress
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import axios from 'axios';

const Opportunities = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchOpportunities = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/trading/opportunities');
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
    return direction === 'LONG' ? 'success' : 'error';
  };

  const getDirectionIcon = (direction) => {
    return direction === 'LONG' ? <TrendingUpIcon /> : <TrendingDownIcon />;
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
        <Tooltip title="Refresh">
          <IconButton onClick={fetchOpportunities} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell>Direction</TableCell>
              <TableCell>Entry Price</TableCell>
              <TableCell>Stop Loss</TableCell>
              <TableCell>Take Profit</TableCell>
              <TableCell>Score</TableCell>
              <TableCell>Risk/Reward</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {opportunities.map((opp) => (
              <TableRow key={opp.symbol}>
                <TableCell>{opp.symbol}</TableCell>
                <TableCell>
                  <Chip
                    icon={getDirectionIcon(opp.direction)}
                    label={opp.direction}
                    color={getDirectionColor(opp.direction)}
                    size="small"
                  />
                </TableCell>
                <TableCell>${opp.entry_price.toFixed(2)}</TableCell>
                <TableCell>${opp.stop_loss.toFixed(2)}</TableCell>
                <TableCell>${opp.take_profit.toFixed(2)}</TableCell>
                <TableCell>
                  <Chip
                    label={`${(opp.score * 100).toFixed(1)}%`}
                    color={opp.score > 0.7 ? 'success' : opp.score > 0.4 ? 'warning' : 'error'}
                    size="small"
                  />
                </TableCell>
                <TableCell>{opp.risk_reward.toFixed(2)}</TableCell>
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
    </Box>
  );
};

export default Opportunities; 