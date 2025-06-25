import React, { useState } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useMediaQuery } from '@mui/system';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SpeedIcon from '@mui/icons-material/Speed';
import GridOnIcon from '@mui/icons-material/GridOn';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import ViewListIcon from '@mui/icons-material/ViewList';
import TimelineIcon from '@mui/icons-material/Timeline';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SettingsIcon from '@mui/icons-material/Settings';

const Navbar = () => {
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileMenuAnchor, setMobileMenuAnchor] = useState(null);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
    { path: '/signals', label: 'Signals', icon: <SignalCellularAltIcon /> },
    { path: '/opportunities', label: 'Opportunities', icon: <TrendingUpIcon /> },
    { path: '/scalping', label: 'Scalping', icon: <SpeedIcon /> },
    { path: '/paper-trading', label: 'Paper Trading', icon: <PsychologyIcon /> },
    { path: '/flow-trading', label: 'Flow Trading', icon: <GridOnIcon /> },
    { path: '/profit-scraping', label: 'Profit Scraping', icon: <MonetizationOnIcon /> },
    { path: '/positions', label: 'Positions', icon: <AccountBalanceWalletIcon /> },
    { path: '/strategies', label: 'Strategies', icon: <ViewListIcon /> },
    { path: '/backtesting', label: 'Backtesting', icon: <TimelineIcon /> },
    { path: '/learning', label: 'Learning', icon: <PsychologyIcon /> },
    { path: '/performance', label: 'Performance', icon: <AssessmentIcon /> },
    { path: '/settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  const handleMobileMenuOpen = (event) => {
    setMobileMenuAnchor(event.currentTarget);
  };

  const handleMobileMenuClose = () => {
    setMobileMenuAnchor(null);
  };

  return (
    <AppBar position="static" color="default" elevation={1}>
      <Container maxWidth="xl" sx={{ px: { xs: 1, sm: 2 } }}>
        <Toolbar 
          disableGutters 
          sx={{ 
            minHeight: { xs: 56, sm: 64 },
            px: 0
          }}
        >
          {/* Logo/Title */}
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{
              mr: { xs: 1, sm: 4 },
              fontWeight: 700,
              color: 'inherit',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              fontSize: { xs: '1rem', sm: '1.25rem' },
              flexShrink: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: { xs: '160px', sm: 'none' }
            }}
          >
            {isMobile ? 'Trading Bot' : 'Crypto Trading Bot'}
          </Typography>

          {/* Desktop Navigation */}
          {!isMobile && (
            <Box sx={{ flexGrow: 1, display: 'flex', gap: 1, overflow: 'hidden' }}>
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
                    px: { sm: 1, md: 2 },
                    fontSize: { sm: '0.8rem', md: '0.875rem' },
                    minWidth: 'auto',
                    flexShrink: 0
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>
          )}

          {/* Mobile Navigation */}
          {isMobile && (
            <>
              <Box sx={{ flexGrow: 1 }} />
              <IconButton
                edge="end"
                color="inherit"
                aria-label="menu"
                onClick={handleMobileMenuOpen}
                sx={{ p: 1 }}
              >
                <MenuIcon />
              </IconButton>
              <Menu
                anchorEl={mobileMenuAnchor}
                open={Boolean(mobileMenuAnchor)}
                onClose={handleMobileMenuClose}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                PaperProps={{
                  sx: {
                    width: 200,
                    maxWidth: '90vw'
                  }
                }}
              >
                {navItems.map((item) => (
                  <MenuItem
                    key={item.path}
                    component={RouterLink}
                    to={item.path}
                    onClick={handleMobileMenuClose}
                    selected={location.pathname === item.path}
                    sx={{
                      color: location.pathname === item.path ? 'primary.main' : 'inherit',
                    }}
                  >
                    <ListItemIcon sx={{ color: 'inherit', minWidth: 36 }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText 
                      primary={item.label}
                      primaryTypographyProps={{
                        fontSize: '0.875rem'
                      }}
                    />
                  </MenuItem>
                ))}
              </Menu>
            </>
          )}
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navbar; 