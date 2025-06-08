import React from 'react';
import {
  Box,
  Typography,
  Chip,
  Grid,
  Divider,
} from '@mui/material';

const SignalChart = ({ signal }) => {
  const getRegimeColor = (regime) => {
    switch (regime) {
      case 'TRENDING': return 'success';
      case 'RANGING': return 'info';
      case 'VOLATILE': return 'warning';
      default: return 'default';
    }
  };

  const getTimeframeColor = (strength) => {
    if (strength >= 0.8) return 'success';
    if (strength >= 0.6) return 'info';
    return 'warning';
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">{signal.symbol}</Typography>
        <Box display="flex" gap={1}>
          <Chip
            label={signal.signal_type}
            color={signal.signal_type === 'LONG' ? 'success' : 'error'}
            size="small"
          />
          <Chip
            label={signal.regime}
            color={getRegimeColor(signal.regime)}
            size="small"
          />
        </Box>
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={6}>
          <Typography color="textSecondary" variant="body2">
            Strategy
          </Typography>
          <Typography variant="body1">
            {signal.strategy || 'Unknown'}
          </Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography color="textSecondary" variant="body2">
            Confidence
          </Typography>
          <Typography variant="body1" color={signal.confidence >= 0.7 ? 'success.main' : 'warning.main'}>
            {((signal.confidence || 0) * 100).toFixed(1)}%
          </Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography color="textSecondary" variant="body2">
            Price
          </Typography>
          <Typography variant="body1">
            ${(signal.price || 0).toFixed(2)}
          </Typography>
        </Grid>

        {/* Multi-timeframe Alignment */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
          <Typography color="textSecondary" variant="body2" gutterBottom>
            Timeframe Alignment
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {signal.mtf_alignment?.details && Object.entries(signal.mtf_alignment.details).map(([tf, data]) => (
              <Chip
                key={tf}
                label={`${tf}: ${data.direction}`}
                color={getTimeframeColor(data.strength)}
                size="small"
              />
            ))}
          </Box>
        </Grid>

        {/* Market Regime Details */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
          <Typography color="textSecondary" variant="body2" gutterBottom>
            Market Regime Details
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {signal.regime === 'TRENDING' && (
              <>
                <Chip
                  label={`ADX: ${signal.indicators?.adx?.value?.toFixed(1) || 'N/A'}`}
                  color="success"
                  size="small"
                />
                <Chip
                  label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                  color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                  size="small"
                />
              </>
            )}
            {signal.regime === 'RANGING' && (
              <>
                <Chip
                  label={`BB Width: ${signal.indicators?.bollinger_bands?.width?.toFixed(3) || 'N/A'}`}
                  color="info"
                  size="small"
                />
                <Chip
                  label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                  color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                  size="small"
                />
              </>
            )}
            {signal.regime === 'VOLATILE' && (
              <>
                <Chip
                  label={`ATR: ${signal.indicators?.atr?.toFixed(2) || 'N/A'}`}
                  color="warning"
                  size="small"
                />
                <Chip
                  label={`Confidence: ${(signal.regime_confidence * 100).toFixed(0)}%`}
                  color={signal.regime_confidence > 0.7 ? "success" : "warning"}
                  size="small"
                />
              </>
            )}
            {signal.is_transitioning && (
              <Chip
                label="Regime Transition"
                color="warning"
                size="small"
              />
            )}
          </Box>
          {signal.regime_scores && (
            <Box mt={1}>
              <Typography variant="caption" color="textSecondary">
                Regime Scores: {Object.entries(signal.regime_scores)
                  .map(([regime, score]) => `${regime}: ${(score * 100).toFixed(0)}%`)
                  .join(' | ')}
              </Typography>
            </Box>
          )}
        </Grid>

        {/* Signal Reasons */}
        {signal.reasons && signal.reasons.length > 0 && (
          <Grid item xs={12}>
            <Divider sx={{ my: 1 }} />
            <Typography color="textSecondary" variant="body2" gutterBottom>
              Signal Reasons
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap">
              {signal.reasons.map((reason, index) => (
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

        {/* Time */}
        <Grid item xs={12}>
          <Typography color="textSecondary" variant="body2" align="right">
            {new Date(signal.timestamp).toLocaleTimeString()}
          </Typography>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SignalChart; 