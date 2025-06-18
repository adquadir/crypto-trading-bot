import config from '../config';

export const createWebSocket = (endpoint) => {
    const apiKey = process.env.REACT_APP_API_KEY;
    if (!apiKey) {
        console.error('API key not found in environment variables');
        return null;
    }
    
    const wsUrl = `${config.WS_BASE_URL}${endpoint}?api_key=${apiKey}`;
    console.log('Connecting to WebSocket:', wsUrl);
    return new WebSocket(wsUrl);
}; 