import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import config, { getWsBaseUrl } from '../config';

const WebSocketContext = createContext(null);

// Hardcoded API key to match backend
const API_KEY = 'crypto_trading_bot_api_key_2024'.trim();

export const WebSocketProvider = ({ children }) => {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [lastMessage, setLastMessage] = useState(null);

  const connectWebSocket = useCallback(() => {
    try {
      // Close existing connection if any
      if (ws) {
        ws.close();
      }

      // Create new WebSocket instance with API key
      const wsUrl = `${getWsBaseUrl()}${config.ENDPOINTS.WS_SIGNALS}?api_key=${encodeURIComponent(API_KEY)}`;
      console.log('Connecting to WebSocket with URL:', wsUrl);
      console.log('API key being sent:', API_KEY);
      console.log('API key length:', API_KEY.length);
      const newWs = new WebSocket(wsUrl);
      
      newWs.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setReconnectAttempt(0);
      };

      newWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      newWs.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };

      newWs.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        
        // Don't reconnect if closed due to invalid API key
        if (event.code === 4003) {
          console.error('WebSocket closed due to invalid API key');
          return;
        }
        
        // Implement exponential backoff for reconnection
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000);
        setTimeout(() => {
          setReconnectAttempt(prev => prev + 1);
          connectWebSocket();
        }, delay);
      };

      // Update the WebSocket instance in state
      setWs(newWs);
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }, [ws, reconnectAttempt]);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [connectWebSocket]);

  const value = {
    ws,
    isConnected,
    lastMessage,
    reconnect: connectWebSocket
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}; 