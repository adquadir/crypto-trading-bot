import React from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  useTheme,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SettingsIcon from '@mui/icons-material/Settings';

const Navbar = () => {
  const location = useLocation();
  const theme = useTheme();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
    { path: '/signals', label: 'Signals', icon: <SignalCellularAltIcon /> },
    { path: '/opportunities', label: 'Opportunities', icon: <TrendingUpIcon /> },
    { path: '/settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  return (
    <AppBar position="static" color="default" elevation={1}>
      <Container maxWidth="xl">
        <Toolbar disableGutters>
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{
              mr: 4,
              fontWeight: 700,
              color: 'inherit',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            Crypto Trading Bot
          </Typography>

          <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
            {navItems.map((item) => (
              <Button
                key={item.path}
                component={RouterLink}
                to={item.path}
                startIcon={item.icon}
                sx={{
                  color: location.pathname === item.path ? 'primary.main' : 'text.secondary',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                  px: 2,
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navbar; 