import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
// import { WebSocketProvider } from './contexts/WebSocketContext';  // Disabled WebSocket
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Signals from './pages/Signals';
import Opportunities from './components/Opportunities';
import Settings from './pages/Settings';

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
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Router>
    </ThemeProvider>
  );
}

export default App; 