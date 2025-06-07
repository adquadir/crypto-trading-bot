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

const getWsBaseUrl = () => {
    const hostname = window.location.hostname;
    const isDevelopment = process.env.NODE_ENV === 'development';

    if (isDevelopment || hostname === 'localhost' || hostname === '127.0.0.1') {
        return `ws://${hostname}:8000`; // Default to port 8000 for local dev
    }
    return `ws://${hostname}:8000`; // Or ws:// followed by window.location.host
};

const config = {
    API_BASE_URL: getApiBaseUrl(),
    WS_BASE_URL: getWsBaseUrl(),
    ENDPOINTS: {
        STATS: '/api/trading/stats',
        POSITIONS: '/api/trading/positions',
        STRATEGIES: '/api/trading/strategies',
        SETTINGS: '/api/trading/settings',
        SIGNALS: '/api/trading/signals',
        WS_SIGNALS: '/ws/signals',
        OPPORTUNITIES: '/api/trading/opportunities',
        OPPORTUNITY_STATS: '/api/trading/opportunities/stats',
        SYMBOL_OPPORTUNITY: (symbol) => `/api/trading/opportunities/${symbol}`
    }
};

export default config; 