import React, { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';
import OpportunitiesComponent from '../components/Opportunities';
import axios from 'axios';
import config from '../config';

const Opportunities = () => {
  const [opportunities, setOpportunities] = useState([]);
  const [error, setError] = useState(null);

  const fetchOpportunities = async () => {
    try {
      const response = await axios.get(`${config.API_BASE_URL}${config.ENDPOINTS.OPPORTUNITIES}`);
      setOpportunities(response.data.data);
    } catch (error) {
      console.error('Error fetching opportunities:', error);
      setError('Failed to fetch opportunities');
    }
  };

  useEffect(() => {
    fetchOpportunities();
  }, []);

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