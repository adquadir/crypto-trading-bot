// Backend API configuration
export const API_CONFIG = {
    // VPS IP address
    BASE_URL: 'http://50.31.0.105:8000',
    // WebSocket URL for real-time updates
    WS_URL: 'ws://50.31.0.105:8000/ws/signals',
    // API endpoints
    ENDPOINTS: {
        STATS: '/api/trading/stats',
        PNL: '/api/trading/pnl',
        POSITIONS: '/api/trading/positions',
        SIGNALS: '/api/trading/signals',
        STRATEGIES: '/api/trading/strategies'
    }
}; 