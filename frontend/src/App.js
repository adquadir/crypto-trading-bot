import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';

// Layout components
import DashboardLayout from './layouts/DashboardLayout';

// Pages
import Dashboard from './pages/Dashboard';
import Signals from './pages/Signals';
import Positions from './pages/Positions';
import Strategies from './pages/Strategies';
import Settings from './pages/Settings';
import Opportunities from './pages/Opportunities';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#0a1929',
      paper: '#132f4c',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Box sx={{ display: 'flex' }}>
          <DashboardLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/opportunities" element={<Opportunities />} />
              <Route path="/signals" element={<Signals />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </DashboardLayout>
        </Box>
      </Router>
    </ThemeProvider>
  );
}

export default App; 