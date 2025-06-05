import React from 'react';
import { Box, Typography } from '@mui/material';
import OpportunitiesComponent from '../components/Opportunities';

const Opportunities = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Trading Opportunities
      </Typography>
      <OpportunitiesComponent />
    </Box>
  );
};

export default Opportunities; 