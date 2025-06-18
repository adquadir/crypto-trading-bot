// Backend API configuration
const getApiBaseUrl = () => {
    // In development, you might want to specify a different host/port
    // For production, it will typically be on the same domain as the frontend
    const hostname = window.location.hostname;
    const isDevelopment = process.env.NODE_ENV === 'development';

    // If running in development (e.g., through Create React App dev server)
    // or if the backend is on a different port/subdomain in production
    if (isDevelopment || hostname === 'localhost' || hostname === '127.0.0.1') {
        return `http://${hostname}:8000`; // Default to port 8000 for local dev
    } 
    // For production, assume backend is on the same domain/port as frontend, or adjust as needed
    return `http://${hostname}:8000`; // Or window.location.origin if backend is on same port
};

// WebSocket functionality disabled
export const getWsBaseUrl = () => {
    return null;
};

const config = {
    API_BASE_URL: getApiBaseUrl(),
    WS_BASE_URL: getWsBaseUrl(),
    ENDPOINTS: {
        STATS: '/api/v1/trading/stats',
        POSITIONS: '/api/v1/trading/positions',
        STRATEGIES: '/api/v1/trading/strategies',
        SETTINGS: '/api/v1/trading/settings',
        SIGNALS: '/api/v1/trading/opportunities',  // Use opportunities as signals
        WS_SIGNALS: '/ws/signals',
        OPPORTUNITIES: '/api/v1/trading/opportunities',
        OPPORTUNITY_STATS: '/api/v1/trading/opportunities/stats',
        SYMBOL_OPPORTUNITY: (symbol) => `/api/v1/trading/opportunities/${symbol}`,
        EXECUTE_MANUAL_TRADE: '/api/v1/trading/execute_manual_trade'
    },
    // API endpoints - WebSocket disabled
    API_URL: process.env.REACT_APP_API_URL || null,
    API_KEY: process.env.REACT_APP_API_KEY,
    RECONNECT_INTERVAL: 5000,
    MAX_RECONNECT_ATTEMPTS: 5,
    
    // WebSocket settings
    wsReconnectDelay: 1000,
    wsMaxReconnectAttempts: 5,
    
    // Data freshness thresholds (in seconds)
    freshnessThresholds: {
        ohlcv: 5,
        orderbook: 2,
        trades: 2,
        ticker: 2,
        openInterest: 5,
        fundingRate: 60
    },
    
    // UI settings
    defaultTimeframe: '1m',
    availableTimeframes: ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'],
    
    // Chart settings
    chartDefaults: {
        height: 400,
        maintainAspectRatio: false,
        animation: false,
        responsive: true
    },
    
    // Table settings
    tableDefaults: {
        pageSize: 10,
        pageSizeOptions: [10, 25, 50, 100]
    }
};

export default config; 
