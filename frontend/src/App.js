import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { useMediaQuery } from '@mui/material';
// import { WebSocketProvider } from './contexts/WebSocketContext';
import { ScalpingWebSocketProvider } from './contexts/ScalpingWebSocketContext';  // Disabled WebSocket
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

// Create enhanced mobile-responsive theme
const createResponsiveTheme = () => {
  const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  return createTheme({
    palette: {
      mode: 'dark',
      primary: {
        main: '#90caf9',
        light: '#e3f2fd',
        dark: '#42a5f5',
      },
      secondary: {
        main: '#f48fb1',
        light: '#fce4ec',
        dark: '#e91e63',
      },
      background: {
        default: '#121212',
        paper: '#1e1e1e',
      },
      success: {
        main: '#4caf50',
        light: '#81c784',
        dark: '#388e3c',
      },
      error: {
        main: '#f44336',
        light: '#e57373',
        dark: '#d32f2f',
      },
      warning: {
        main: '#ff9800',
        light: '#ffb74d',
        dark: '#f57c00',
      },
      info: {
        main: '#2196f3',
        light: '#64b5f6',
        dark: '#1976d2',
      },
    },
    typography: {
      // Mobile-optimized typography
      fontFamily: [
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        '"Helvetica Neue"',
        'Arial',
        'sans-serif',
      ].join(','),
      h1: {
        fontSize: '2rem',
        '@media (min-width:600px)': {
          fontSize: '2.5rem',
        },
        '@media (min-width:960px)': {
          fontSize: '3rem',
        },
        fontWeight: 700,
        lineHeight: 1.2,
      },
      h2: {
        fontSize: '1.75rem',
        '@media (min-width:600px)': {
          fontSize: '2rem',
        },
        '@media (min-width:960px)': {
          fontSize: '2.25rem',
        },
        fontWeight: 600,
        lineHeight: 1.3,
      },
      h3: {
        fontSize: '1.5rem',
        '@media (min-width:600px)': {
          fontSize: '1.75rem',
        },
        '@media (min-width:960px)': {
          fontSize: '2rem',
        },
        fontWeight: 600,
        lineHeight: 1.3,
      },
      h4: {
        fontSize: '1.25rem',
        '@media (min-width:600px)': {
          fontSize: '1.5rem',
        },
        '@media (min-width:960px)': {
          fontSize: '1.75rem',
        },
        fontWeight: 600,
        lineHeight: 1.4,
      },
      h5: {
        fontSize: '1.125rem',
        '@media (min-width:600px)': {
          fontSize: '1.25rem',
        },
        fontWeight: 500,
        lineHeight: 1.4,
      },
      h6: {
        fontSize: '1rem',
        '@media (min-width:600px)': {
          fontSize: '1.125rem',
        },
        fontWeight: 500,
        lineHeight: 1.4,
      },
      body1: {
        fontSize: '0.875rem',
        '@media (min-width:600px)': {
          fontSize: '1rem',
        },
        lineHeight: 1.5,
      },
      body2: {
        fontSize: '0.75rem',
        '@media (min-width:600px)': {
          fontSize: '0.875rem',
        },
        lineHeight: 1.4,
      },
      caption: {
        fontSize: '0.625rem',
        '@media (min-width:600px)': {
          fontSize: '0.75rem',
        },
        lineHeight: 1.3,
      },
      button: {
        fontSize: '0.875rem',
        '@media (min-width:600px)': {
          fontSize: '0.875rem',
        },
        fontWeight: 500,
        textTransform: 'none', // More modern look
      },
    },
    spacing: 8, // Base spacing unit
    breakpoints: {
      values: {
        xs: 0,
        sm: 600,
        md: 900,
        lg: 1200,
        xl: 1536,
      },
    },
    components: {
      // Mobile-optimized component overrides
      MuiContainer: {
        styleOverrides: {
          root: {
            paddingLeft: '8px',
            paddingRight: '8px',
            '@media (min-width:600px)': {
              paddingLeft: '16px',
              paddingRight: '16px',
            },
            '@media (min-width:900px)': {
              paddingLeft: '24px',
              paddingRight: '24px',
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: '12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            '@media (max-width:600px)': {
              borderRadius: '8px',
              margin: '4px',
            },
          },
        },
      },
      MuiCardContent: {
        styleOverrides: {
          root: {
            padding: '12px',
            '@media (min-width:600px)': {
              padding: '16px',
            },
            '@media (min-width:900px)': {
              padding: '24px',
            },
            '&:last-child': {
              paddingBottom: '12px',
              '@media (min-width:600px)': {
                paddingBottom: '16px',
              },
              '@media (min-width:900px)': {
                paddingBottom: '24px',
              },
            },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: '8px',
            minHeight: '44px', // Touch-friendly minimum
            '@media (max-width:600px)': {
              minHeight: '48px', // Even larger on mobile for better touch
              fontSize: '0.875rem',
            },
          },
          contained: {
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
            '&:hover': {
              boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              padding: '12px', // Larger touch targets on mobile
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              fontSize: '0.75rem',
              height: '24px',
            },
          },
          sizeSmall: {
            '@media (max-width:600px)': {
              fontSize: '0.625rem',
              height: '20px',
            },
          },
        },
      },
      MuiTableContainer: {
        styleOverrides: {
          root: {
            '@media (max-width:900px)': {
              overflowX: 'auto',
              '&::-webkit-scrollbar': {
                height: '6px',
              },
              '&::-webkit-scrollbar-track': {
                backgroundColor: 'rgba(255,255,255,0.1)',
              },
              '&::-webkit-scrollbar-thumb': {
                backgroundColor: 'rgba(255,255,255,0.3)',
                borderRadius: '3px',
              },
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              padding: '8px 4px',
              fontSize: '0.75rem',
            },
            '@media (min-width:600px) and (max-width:900px)': {
              padding: '12px 8px',
              fontSize: '0.875rem',
            },
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            '@media (max-width:600px)': {
              margin: '16px',
              width: 'calc(100% - 32px)',
              maxHeight: 'calc(100% - 64px)',
            },
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              fontSize: '1.125rem',
              padding: '16px',
            },
          },
        },
      },
      MuiDialogContent: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              padding: '8px 16px',
            },
          },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              padding: '8px 16px 16px',
              flexDirection: 'column',
              '& > :not(:first-of-type)': {
                marginLeft: 0,
                marginTop: '8px',
              },
            },
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              '& .MuiInputBase-root': {
                fontSize: '16px', // Prevents zoom on iOS
              },
            },
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              fontSize: '16px', // Prevents zoom on iOS
            },
          },
        },
      },
      MuiFormControl: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              minWidth: '100%',
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              '& .MuiTab-root': {
                minWidth: '80px',
                fontSize: '0.75rem',
                padding: '8px 12px',
              },
            },
          },
          scrollButtons: {
            '@media (max-width:600px)': {
              width: '32px',
            },
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              '& .MuiToolbar-root': {
                minHeight: '56px',
                paddingLeft: '8px',
                paddingRight: '8px',
              },
            },
          },
        },
      },
    },
  });
};

function App() {
  const theme = createResponsiveTheme();

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ScalpingWebSocketProvider>
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
      </ScalpingWebSocketProvider>
    </ThemeProvider>
  );
}

export default App; 