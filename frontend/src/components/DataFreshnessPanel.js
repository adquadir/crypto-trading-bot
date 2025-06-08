import React from 'react';
import {
  Box,
  Typography,
  Chip,
  Grid,
  Card,
  CardHeader,
  CardContent,
} from '@mui/material';

const DataFreshnessPanel = ({ signal }) => {
  const getFreshnessColor = (age, maxAge) => {
    const ratio = age / maxAge;
    if (ratio < 0.5) return 'success';
    if (ratio < 0.8) return 'warning';
    return 'error';
  };

  const formatAge = (age) => {
    if (age < 1) return `${(age * 1000).toFixed(0)}ms`;
    return `${age.toFixed(1)}s`;
  };

  if (!signal?.data_freshness) return null;

  return (
    <Card>
      <CardHeader title="Data Freshness" />
      <CardContent>
        <Grid container spacing={2}>
          {Object.entries(signal.data_freshness).map(([type, age]) => (
            <Grid item xs={6} key={type}>
              <Box display="flex" alignItems="center">
                <Typography variant="body2" style={{ marginRight: 8 }}>
                  {type}:
                </Typography>
                <Chip
                  label={formatAge(age)}
                  color={getFreshnessColor(age, signal.max_allowed_freshness?.[type] || 10)}
                  size="small"
                />
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
};

export default DataFreshnessPanel; 