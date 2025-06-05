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
        WS_SIGNALS: '/ws/signals'
    }
};

export default config; 