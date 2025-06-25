import React from 'react';
import { Box, Typography, Container, useTheme, useMediaQuery } from '@mui/material';
import OpportunitiesComponent from '../components/Opportunities';

const Opportunities = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  return (
    <Container maxWidth="xl" sx={{ py: { xs: 1, sm: 2, md: 3 } }}>
      <Box mb={{ xs: 2, sm: 3 }}>
        <Typography 
          variant={isMobile ? "h5" : "h4"} 
          gutterBottom 
          fontWeight="bold"
          sx={{ 
            fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' }
          }}
        >
        Trading Opportunities
      </Typography>
        <Typography 
          variant="body1" 
          color="text.secondary"
          sx={{ 
            fontSize: { xs: '0.875rem', sm: '1rem' }
          }}
        >
          Real-time market opportunities with precision analysis
        </Typography>
      </Box>
      <OpportunitiesComponent />
    </Container>
  );
};

export default Opportunities; 