import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
// import { WebSocketProvider } from './contexts/WebSocketContext';  // Disabled WebSocket
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Signals from './pages/Signals';
import Opportunities from './pages/Opportunities';
import Scalping from './pages/Scalping';
import Settings from './pages/Settings';
import Performance from './pages/Performance';
import Backtesting from './pages/Backtesting';
import Learning from './pages/Learning';

// Layout components
import DashboardLayout from './layouts/DashboardLayout';

// Pages
import Positions from './pages/Positions';
import Strategies from './pages/Strategies';

// Create theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
        <Router>
          <Navbar />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/opportunities" element={<Opportunities />} />
            <Route path="/scalping" element={<Scalping />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/performance" element={<Performance />} />
                          <Route path="/backtesting" element={<Backtesting />} />
              <Route path="/learning" element={<Learning />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Router>
    </ThemeProvider>
  );
}

export default App; 