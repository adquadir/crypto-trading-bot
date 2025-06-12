import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import config, { getWsBaseUrl } from '../config';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [lastMessage, setLastMessage] = useState(null);

  const connectWebSocket = useCallback(() => {
    // Close existing connection if any
    if (ws) {
      ws.close();
    }

    // Create new WebSocket instance
    const ws = new WebSocket(getWsBaseUrl());
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setReconnectAttempt(0);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      
      // Implement exponential backoff for reconnection
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000);
      setTimeout(() => {
        setReconnectAttempt(prev => prev + 1);
        connectWebSocket();
      }, delay);
    };

    // Update the WebSocket instance in state
    setWs(ws);
  }, [ws, reconnectAttempt]);

  useEffect(() => {
    if (!ws) {
      connectWebSocket();
    }
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [ws, connectWebSocket]);

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