// Backend API configuration
const config = {
    API_BASE_URL: 'http://50.31.0.105:8000',
    WS_BASE_URL: 'ws://50.31.0.105:8000',
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