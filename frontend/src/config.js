// Backend API configuration
const getApiBaseUrl = () => {
    // In development, you might want to specify a different host/port
    // For production, it will typically be on the same domain as the frontend
    const hostname = window.location.hostname;
    const isDevelopment = process.env.NODE_ENV === 'development';

    // If running in development (e.g., through Create React App dev server)
    // or if the backend is on a different port/subdomain in production
    if (isDevelopment || hostname === 'localhost' || hostname === '127.0.0.1') {
        return `http://${hostname}:8000`; // FIXED: Use port 8000 where backend is running
    } 
    // For production, assume backend is on the same domain/port as frontend, or adjust as needed
    return `http://${hostname}:8000`; // FIXED: Use port 8000 where backend is running
};

// WebSocket configuration - ENABLED
export const getWsBaseUrl = () => {
    const hostname = window.location.hostname;
    const isDevelopment = process.env.NODE_ENV === 'development';

    // Use WebSocket protocol instead of HTTP
    if (isDevelopment || hostname === 'localhost' || hostname === '127.0.0.1') {
        return `ws://${hostname}:8000`; // FIXED: WebSocket port 8000 to match backend
    }
    return `ws://${hostname}:8000`; // FIXED: WebSocket on port 8000 to match backend
};

const config = {
    API_BASE_URL: getApiBaseUrl(),
    WS_BASE_URL: getWsBaseUrl(),
    ENDPOINTS: {
        STATS: '/api/v1/stats',
        POSITIONS: '/api/v1/paper-trading/positions',
        STRATEGIES: '/api/v1/strategies',
        SETTINGS: '/api/v1/settings',
        SIGNALS: '/api/v1/opportunities',  // Use opportunities as signals
        WS_SIGNALS: '/ws/signals',
        OPPORTUNITIES: '/api/v1/opportunities',
        OPPORTUNITY_STATS: '/api/v1/opportunities/stats',
        SYMBOL_OPPORTUNITY: (symbol) => `/api/v1/opportunities/${symbol}`,
        EXECUTE_MANUAL_TRADE: '/api/v1/execute_manual_trade',
        
        // Profit Scraping endpoints
        PROFIT_SCRAPING: {
            STATUS: '/api/v1/profit-scraping/status',
            START: '/api/v1/profit-scraping/start',
            STOP: '/api/v1/profit-scraping/stop',
            OPPORTUNITIES: '/api/v1/profit-scraping/opportunities',
            ACTIVE_TRADES: '/api/v1/profit-scraping/active-trades',
            RECENT_TRADES: '/api/v1/profit-scraping/trades/recent',
            PERFORMANCE: '/api/v1/profit-scraping/performance',
            LEVELS: (symbol) => `/api/v1/profit-scraping/levels/${symbol}`,
            ANALYZE: (symbol) => `/api/v1/profit-scraping/analyze/${symbol}`
        },
        
        // Paper Trading endpoints
        PAPER_TRADING: {
            STATUS: '/api/v1/paper-trading/status',
            START: '/api/v1/paper-trading/start',
            STOP: '/api/v1/paper-trading/stop',
            POSITIONS: '/api/v1/paper-trading/positions',
            PERFORMANCE: '/api/v1/paper-trading/performance',
            TRADES: '/api/v1/paper-trading/trades',
            ACCOUNT: '/api/v1/paper-trading/account'
        }
    },
    // API endpoints - WebSocket disabled
    API_URL: process.env.REACT_APP_API_URL || null,
    API_KEY: process.env.REACT_APP_API_KEY || 'crypto_trading_api_key_2024',
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
